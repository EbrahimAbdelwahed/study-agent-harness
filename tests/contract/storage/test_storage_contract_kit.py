from __future__ import annotations

import inspect
import sqlite3
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import cast

import pytest

from study_agent.adapters.filesystem import (
    BlobIntegrityError,
    BlobNotFoundError,
    FilesystemBlobStore,
)
from study_agent.adapters.memory import (
    DeterministicIdFactory,
    FixedClock,
    MemoryBlobStore,
    MemoryEventStore,
    MemoryRepository,
    MemoryRunStore,
)
from study_agent.adapters.sqlite import SQLiteEventStore, SQLiteRunStore
from study_agent.api import storage
from study_agent.domain import Actor, BlobId, BlobRef, CorrelationId, CourseId, DomainEvent
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.errors import (
    ConflictFailure,
    InternalFailure,
    NotFoundFailure,
    StaleFailure,
    UnauthorizedFailure,
    UnavailableDependencyFailure,
    ValidationFailure,
)
from study_agent.domain.events import EventEnvelope, PrincipalKind
from study_agent.domain.identifiers import RunId
from study_agent.ports.storage import (
    BlobStore,
    CourseStreamHighWater,
    CourseStreamHighWaterPort,
    EventSequenceConflictError,
    EventStore,
    IdempotencyConflictError,
    Repository,
    RunNotFoundError,
    RunStore,
    RunStoreConflictFailure,
)
from study_agent.state import EventRegistry


def _event(stream: CourseId, sequence: int, *, event_id: str | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id or f"event-{sequence}",
        "counter.incremented",
        1,
        stream,
        sequence,
        datetime(2026, 8, 9, 12, sequence, tzinfo=UTC),
        CorrelationId("correlation-1"),
        Actor(PrincipalKind.SERVICE, "contract"),
        {"amount": sequence},
    )


def test_all_six_host_ports_are_importable_without_provider_types() -> None:
    names = ("EventStore", "BlobStore", "RunStore", "Repository", "Clock", "IdFactory")
    for name in names:
        port = getattr(storage, name)
        assert inspect.isclass(port)
        assert getattr(port, "__module__", "").startswith("study_agent.")


def test_course_stream_high_water_is_exposed_without_provider_types() -> None:
    assert storage.CourseStreamHighWater is CourseStreamHighWater
    assert storage.CourseStreamHighWaterPort is CourseStreamHighWaterPort
    assert inspect.isclass(storage.CourseStreamHighWater)
    assert inspect.isclass(storage.CourseStreamHighWaterPort)


@pytest.mark.parametrize("kind", ("memory", "sqlite"))
def test_event_store_high_water_is_typed_course_bound_and_empty_zero(
    kind: str, tmp_path: Path
) -> None:
    stream = CourseId("course-high-water")
    other = CourseId("other-high-water")
    store: EventStore
    if kind == "memory":
        store = MemoryEventStore()
    else:
        store = SQLiteEventStore(tmp_path / "events.sqlite3")

    assert isinstance(store, CourseStreamHighWaterPort)
    assert store.observe_high_water(stream) == CourseStreamHighWater(stream, 0)
    assert store.observe_high_water(other) == CourseStreamHighWater(other, 0)

    store.append(stream, 0, (_event(stream, 1),), idempotency_key="high-water-command")
    assert store.observe_high_water(stream) == CourseStreamHighWater(stream, 1)
    assert store.observe_high_water(other) == CourseStreamHighWater(other, 0)

    with pytest.raises(ValidationFailure):
        store.observe_high_water(cast(CourseId, "course-high-water"))


@pytest.mark.parametrize("sequence", (True, -1, 1.0))
def test_course_stream_high_water_rejects_invalid_sequences(sequence: object) -> None:
    with pytest.raises(ValidationFailure):
        CourseStreamHighWater(CourseId("course-high-water"), cast(int, sequence))


def test_sqlite_high_water_adapter_failure_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    def fail_connect() -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "_connect", fail_connect)
    with pytest.raises(UnavailableDependencyFailure):
        store.observe_high_water(CourseId("course-high-water"))


@pytest.mark.parametrize("kind", ("memory", "sqlite"))
def test_event_store_idempotency_stale_conflict_and_replay_bytes(
    kind: str, tmp_path: Path
) -> None:
    stream = CourseId("course-contract")
    store: EventStore
    if kind == "memory":
        store = MemoryEventStore()
    else:
        store = SQLiteEventStore(tmp_path / "events.sqlite3")

    first = _event(stream, 1)
    second = _event(stream, 1, event_id="stale-command")
    assert store.append(stream, 0, (first,), idempotency_key="command-1") == 1
    assert store.append(stream, 0, (first,), idempotency_key="command-1") == 1
    with pytest.raises(IdempotencyConflictError) as conflict:
        store.append(
            stream,
            0,
            (_event(stream, 1, event_id="changed"),),
            idempotency_key="command-1",
        )
    assert isinstance(conflict.value, ConflictFailure)
    with pytest.raises(EventSequenceConflictError) as stale:
        store.append(stream, 0, (second,), idempotency_key="command-2")
    assert isinstance(stale.value, StaleFailure)
    assert tuple(event.canonical_bytes() for event in store.read(stream)) == (
        first.canonical_bytes(),
    )


@pytest.mark.parametrize("kind", ("memory", "sqlite"))
def test_keyed_empty_stream_is_idempotent_and_unkeyed_public_write_is_rejected(
    kind: str, tmp_path: Path
) -> None:
    stream = CourseId("empty-stream")
    store: EventStore
    if kind == "memory":
        store = MemoryEventStore()
    else:
        store = SQLiteEventStore(tmp_path / "events.sqlite3")
    assert store.append(stream, 0, (), idempotency_key="empty-command") == 0
    assert store.append(stream, 0, (), idempotency_key="empty-command") == 0
    with pytest.raises(ValidationFailure):
        store.append(stream, 0, (_event(stream, 1),))


def _counter_registry() -> EventRegistry:
    registry = EventRegistry()

    def decode(payload: JsonObject) -> int:
        amount = payload.get("amount")
        if not isinstance(amount, int):
            raise ValueError("amount must be an integer")
        return amount

    def reduce_state(
        state: JsonObject, _event: DomainEvent, amount: int
    ) -> Mapping[str, JsonValue]:
        total = state.get("total", 0)
        if not isinstance(total, int):
            raise ValueError("total must be an integer")
        return {"total": total + amount}

    registry.register("counter.incremented", 1, decode, reduce_state)
    return registry


def test_memory_and_sqlite_projection_replay_are_byte_identical(tmp_path: Path) -> None:
    stream = CourseId("projection-replay")
    events = (_event(stream, 1), _event(stream, 2, event_id="event-2"))
    memory = MemoryEventStore(_counter_registry())
    sqlite = SQLiteEventStore(tmp_path / "events.sqlite3", _counter_registry())
    assert memory.append(stream, 0, events, idempotency_key="projection-command") == 2
    assert sqlite.append(stream, 0, events, idempotency_key="projection-command") == 2
    assert memory.projection_bytes(stream) == sqlite.projection_bytes(stream)


def test_sqlite_failed_batch_rolls_back_all_canonical_rows(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    stream = CourseId("rollback")
    first = _event(stream, 1)
    duplicate_id = _event(stream, 2, event_id=str(first.event_id))
    assert store.append(stream, 0, (first,), idempotency_key="rollback-1") == 1
    with pytest.raises(ConflictFailure):
        store.append(stream, 1, (duplicate_id,), idempotency_key="rollback-2")
    assert tuple(event.event_id for event in store.read(stream)) == (first.event_id,)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone() == (1,)


def test_sqlite_read_only_append_maps_to_unauthorized_failure(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    SQLiteEventStore(database)
    store = SQLiteEventStore(database, read_only=True)
    stream = CourseId("read-only")
    with pytest.raises(UnauthorizedFailure):
        store.append(stream, 0, (_event(stream, 1),), idempotency_key="read-only-command")


@pytest.mark.parametrize("factory", (MemoryBlobStore, FilesystemBlobStore))
def test_blob_identity_dedupes_verifies_and_never_overwrites(
    factory: type[MemoryBlobStore] | type[FilesystemBlobStore], tmp_path: Path
) -> None:
    store: BlobStore
    if factory is MemoryBlobStore:
        store = MemoryBlobStore()
    else:
        store = FilesystemBlobStore(tmp_path / "blobs")
    content = b"immutable bytes"
    ref = store.put(content)
    assert store.put(content, ref) == ref
    wrong = BlobRef(
        BlobId(f"sha256:{ref.checksum_sha256}"), ref.checksum_sha256, ref.byte_length + 1
    )
    with pytest.raises((ValueError, InternalFailure, ValidationFailure)):
        store.put(content, wrong)
    assert store.get(ref) == content


def test_filesystem_blob_corruption_maps_to_typed_failures(tmp_path: Path) -> None:
    root = tmp_path / "blobs"
    store = FilesystemBlobStore(root)
    ref = store.put(b"canonical")
    target = (
        root
        / "objects"
        / ref.checksum_sha256[:2]
        / ref.checksum_sha256[2:4]
        / ref.checksum_sha256
    )
    target.chmod(0o644)
    target.write_bytes(b"tampered")
    with pytest.raises(BlobIntegrityError) as corrupted:
        store.get(ref)
    assert isinstance(corrupted.value, InternalFailure)
    target.unlink()
    with pytest.raises(BlobNotFoundError) as missing:
        store.get(ref)
    assert isinstance(missing.value, NotFoundFailure)


@pytest.mark.parametrize("store_factory", (MemoryRunStore, SQLiteRunStore))
def test_operational_run_cas_is_typed_and_noncanonical(
    store_factory: type[MemoryRunStore] | type[SQLiteRunStore], tmp_path: Path
) -> None:
    store: RunStore
    if store_factory is MemoryRunStore:
        store = MemoryRunStore()
    else:
        store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    run_id = RunId("operational")
    assert store.create(run_id, b"running")
    conflict = store.compare_and_set(run_id, b"stale", b"replacement")
    assert isinstance(conflict, RunStoreConflictFailure)
    assert not conflict
    assert store.load(run_id) == b"running"
    with pytest.raises(RunNotFoundError):
        store.load(RunId("missing"))


@pytest.mark.parametrize("store_kind", ("memory", "sqlite"))
def test_concurrent_run_cas_has_one_winner_across_adapters(
    store_kind: str, tmp_path: Path
) -> None:
    store: RunStore
    if store_kind == "memory":
        store = MemoryRunStore()
    else:
        store = SQLiteRunStore(tmp_path / "races.sqlite3")

    run_id = RunId(f"race-{store_kind}")
    assert store.create(run_id, b"initial")
    barrier = Barrier(8)

    def replace(payload: bytes) -> bool | RunStoreConflictFailure:
        barrier.wait()
        return store.compare_and_set(run_id, b"initial", payload)

    payloads = tuple(bytes([index]) for index in range(8))
    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        results = tuple(executor.map(replace, payloads))

    assert results.count(True) == 1
    losers = tuple(result for result in results if result is not True)
    assert len(losers) == len(payloads) - 1
    assert all(isinstance(result, RunStoreConflictFailure) for result in losers)
    assert all(not result for result in losers)
    assert store.load(run_id) in payloads


def test_clock_ids_and_repository_are_explicitly_composed() -> None:
    instant = datetime(2026, 8, 9, 12, tzinfo=UTC)
    clock = FixedClock(instant)
    assert clock.now() == instant
    ids = DeterministicIdFactory("fixture")
    assert str(ids.new(RunId)) == "fixture-1"
    repository = MemoryRepository(MemoryEventStore(), MemoryBlobStore(), MemoryRunStore())
    assert isinstance(repository, Repository)
    assert repository.source_content is None
