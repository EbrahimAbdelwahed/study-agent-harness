from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any
from unittest.mock import Mock

import pytest

from study_agent.adapters.sqlite import (
    SequenceConflictError,
    SQLiteConnectionIdentityError,
    SQLiteEventStore,
)
from study_agent.adapters.sqlite.event_store import SQLITE_BUSY_TIMEOUT_SECONDS
from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import EventEnvelope
from study_agent.ports.storage import (
    CourseStreamHighWater,
    CourseStreamHighWaterPort,
    EventSequenceConflictError,
    _append_legacy,
    _LegacyEventStore,
)
from study_agent.state import EventRegistry


def make_event(course_id: CourseId, sequence: int) -> DomainEvent:
    return DomainEvent(
        EventId(f"event-{sequence}"),
        course_id,
        sequence,
        "counter.incremented",
        1,
        Actor(PrincipalKind.SERVICE, "test-suite"),
        datetime(2026, 7, 10, 12, sequence, tzinfo=UTC),
        CorrelationId("correlation-1"),
        {"amount": sequence},
    )


def registry() -> EventRegistry:
    result = EventRegistry()

    def decode(payload: JsonObject) -> int:
        amount = payload.get("amount")
        if not isinstance(amount, int):
            raise ValueError("amount must be an integer")
        return amount

    def increment(
        state: JsonObject, _: DomainEvent, amount: int
    ) -> Mapping[str, JsonValue]:
        total = state.get("total", 0)
        assert isinstance(total, int)
        return {"total": total + amount}

    result.register("counter.incremented", 1, decode, increment)
    return result


def exercise_event_store_contract(store: _LegacyEventStore) -> None:
    course_id = CourseId("course-contract")
    events = (make_event(course_id, 1), make_event(course_id, 2))

    assert store.read(course_id) == ()
    assert _append_legacy(store, course_id, 0, events) == 2
    public_events = store.read(course_id)
    assert all(isinstance(event, EventEnvelope) for event in public_events)
    assert tuple(event.event_id for event in public_events) == tuple(
        event.event_id for event in events
    )
    assert tuple(event.event_id for event in store.read(course_id, after_sequence=1)) == (
        events[1].event_id,
    )
    assert _append_legacy(store, course_id, 2, ()) == 2


def test_sqlite_adapter_conforms_to_event_store_port(tmp_path: Path) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry())
    exercise_event_store_contract(store)


def test_sqlite_high_water_uses_the_canonical_events_table(tmp_path: Path) -> None:
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database, registry())
    course_id = CourseId("course-high-water")

    assert isinstance(store, CourseStreamHighWaterPort)
    assert store.observe_high_water(course_id) == CourseStreamHighWater(course_id, 0)
    _append_legacy(store, course_id, 0, (make_event(course_id, 1),))
    assert store.observe_high_water(course_id) == CourseStreamHighWater(course_id, 1)

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "events" in tables
    assert not any("high_water" in table for table in tables)


def test_read_only_high_water_observes_live_writer_with_normal_sqlite_locking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    writer = SQLiteEventStore(database, registry())
    course_id = CourseId("course-live-reader")
    _append_legacy(writer, course_id, 0, (make_event(course_id, 1),))
    reader = SQLiteEventStore(database, registry(), read_only=True)

    writer_started = Barrier(2)
    release_writer = Barrier(2)
    original_transaction = writer._transaction

    @contextmanager
    def hold_writer_transaction() -> Iterator[sqlite3.Connection]:
        with original_transaction() as connection:
            writer_started.wait()
            release_writer.wait()
            yield connection

    monkeypatch.setattr(writer, "_transaction", hold_writer_transaction)
    connect_spy = Mock(wraps=sqlite3.connect)
    monkeypatch.setattr(sqlite3, "connect", connect_spy)

    with ThreadPoolExecutor(max_workers=1) as executor:
        append_future = executor.submit(
            _append_legacy, writer, course_id, 1, (make_event(course_id, 2),)
        )
        writer_started.wait()
        assert reader.observe_high_water(course_id) == CourseStreamHighWater(course_id, 1)
        release_writer.wait()
        assert append_future.result() == 2

    assert reader.observe_high_water(course_id) == CourseStreamHighWater(course_id, 2)
    read_only_uris = tuple(
        call.args[0]
        for call in connect_spy.call_args_list
        if call.args
        and isinstance(call.args[0], str)
        and "?mode=ro" in call.args[0]
    )
    assert read_only_uris
    assert all("immutable" not in uri for uri in read_only_uris)
    assert all(uri.endswith("/events.sqlite3?mode=ro&nofollow=1") for uri in read_only_uris)
    assert all(
        call.kwargs.get("timeout") == SQLITE_BUSY_TIMEOUT_SECONDS
        for call in connect_spy.call_args_list
    )


def test_read_only_high_water_rejects_final_symlink(tmp_path: Path) -> None:
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    link = tmp_path / "events.sqlite3"
    first_store = SQLiteEventStore(first)
    second_store = SQLiteEventStore(second)
    course_id = CourseId("course-symlink")
    _append_legacy(first_store, course_id, 0, (make_event(course_id, 1),))
    _append_legacy(
        second_store,
        course_id,
        0,
        (make_event(course_id, 1), make_event(course_id, 2)),
    )
    try:
        link.symlink_to(first)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable: {error}")

    reader = SQLiteEventStore(link, registry(), read_only=True)
    with pytest.raises(SQLiteConnectionIdentityError):
        reader.observe_high_water(course_id)


def test_read_only_high_water_rejects_detectable_b_to_a_transition_after_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    replacement = tmp_path / "replacement.sqlite3"
    original_anchor = tmp_path / "original-anchor.sqlite3"
    original_store = SQLiteEventStore(database, registry())
    replacement_store = SQLiteEventStore(replacement, registry())
    course_id = CourseId("course-concurrent-replacement")
    _append_legacy(original_store, course_id, 0, (make_event(course_id, 1),))
    _append_legacy(
        replacement_store,
        course_id,
        0,
        (make_event(course_id, 1), make_event(course_id, 2)),
    )
    database.rename(original_anchor)
    replacement.replace(database)

    reader = SQLiteEventStore(database, registry(), read_only=True)
    real_connect: Callable[..., sqlite3.Connection] = sqlite3.connect
    race_started = False

    def racing_connect(
        database_argument: str, *args: Any, **kwargs: Any
    ) -> sqlite3.Connection:
        nonlocal race_started
        if race_started or not (
            isinstance(database_argument, str) and "?mode=ro" in database_argument
        ):
            return real_connect(database_argument, *args, **kwargs)

        race_started = True
        connection = real_connect(database_argument, *args, **kwargs)
        original_anchor.replace(database)
        return connection

    monkeypatch.setattr(sqlite3, "connect", racing_connect)
    with pytest.raises(SQLiteConnectionIdentityError):
        reader.observe_high_water(course_id)

    assert race_started
    # This B-to-A transition is detectable from the retained source entry.
    # A/B/restore around xOpen remains outside pathname continuity and is
    # covered below as explicit negative evidence rather than an exact claim.


def test_writable_high_water_documents_unprotectable_a_b_xopen_a_interleaving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    replacement = tmp_path / "replacement.sqlite3"
    original_anchor = tmp_path / "original-anchor.sqlite3"
    original_store = SQLiteEventStore(database, registry())
    replacement_store = SQLiteEventStore(replacement, registry())
    course_id = CourseId("course-unprotectable-replacement")
    _append_legacy(original_store, course_id, 0, (make_event(course_id, 1),))
    _append_legacy(
        replacement_store,
        course_id,
        0,
        (make_event(course_id, 1), make_event(course_id, 2)),
    )

    store = SQLiteEventStore(database, registry())
    real_connect: Callable[..., sqlite3.Connection] = sqlite3.connect
    race_started = False

    def racing_connect(
        database_argument: str, *args: Any, **kwargs: Any
    ) -> sqlite3.Connection:
        nonlocal race_started
        if race_started or not (
            isinstance(database_argument, str) and "?mode=rw" in database_argument
        ):
            return real_connect(database_argument, *args, **kwargs)
        race_started = True
        database.rename(original_anchor)
        replacement.replace(database)
        try:
            connection = real_connect(database_argument, *args, **kwargs)
        finally:
            database.unlink()
            original_anchor.replace(database)
        return connection

    monkeypatch.setattr(sqlite3, "connect", racing_connect)
    assert store.observe_high_water(course_id) == CourseStreamHighWater(course_id, 2)
    assert race_started
    # The path is A again after xOpen, so no pathname-continuity check can
    # recover the transient B handle without a native SQLite VFS.


def test_event_schema_cannot_be_registered_without_a_payload_decoder() -> None:
    result = EventRegistry()

    def reducer(
        state: JsonObject, _: DomainEvent, __: object
    ) -> Mapping[str, JsonValue]:
        return state

    with pytest.raises(TypeError):
        result.register("counter.incremented", 1, reducer)  # type: ignore[call-arg]


def test_sqlite_conflict_implements_portable_sequence_conflict(tmp_path: Path) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3", registry())
    course_id = CourseId("course-conflict")
    _append_legacy(store, course_id, 0, (make_event(course_id, 1),))

    with pytest.raises(EventSequenceConflictError) as caught:
        _append_legacy(store, course_id, 0, ())

    assert isinstance(caught.value, SequenceConflictError)
    assert (caught.value.expected, caught.value.actual) == (0, 1)
