from __future__ import annotations

import inspect
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

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
from study_agent.domain import Actor, BlobId, BlobRef, CorrelationId, CourseId
from study_agent.domain.errors import (
    ConflictFailure,
    InternalFailure,
    NotFoundFailure,
    StaleFailure,
    ValidationFailure,
)
from study_agent.domain.events import EventEnvelope, PrincipalKind
from study_agent.domain.identifiers import RunId
from study_agent.ports.storage import (
    BlobStore,
    EventSequenceConflictError,
    EventStore,
    IdempotencyConflictError,
    Repository,
    RunNotFoundError,
    RunStore,
    RunStoreConflictFailure,
)


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


def test_sqlite_failed_batch_rolls_back_all_canonical_rows(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    stream = CourseId("rollback")
    first = _event(stream, 1)
    duplicate_id = _event(stream, 2, event_id=str(first.event_id))
    assert store.append(stream, 0, (first,)) == 1
    with pytest.raises(ConflictFailure):
        store.append(stream, 1, (duplicate_id,))
    assert tuple(event.event_id for event in store.read(stream)) == (first.event_id,)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone() == (1,)


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


def test_clock_ids_and_repository_are_explicitly_composed() -> None:
    instant = datetime(2026, 8, 9, 12, tzinfo=UTC)
    clock = FixedClock(instant)
    assert clock.now() == instant
    ids = DeterministicIdFactory("fixture")
    assert str(ids.new(RunId)) == "fixture-1"
    repository = MemoryRepository(MemoryEventStore(), MemoryBlobStore(), MemoryRunStore())
    assert isinstance(repository, Repository)
    assert repository.source_content is None
