from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread

import pytest

from study_agent.adapters.sqlite import SequenceConflictError, SQLiteEventStore
from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.events import EventEnvelope
from study_agent.ports.storage import (
    EventSequenceConflictError,
    _append_legacy,
    _LegacyEventStore,
)
from study_agent.state import EventRegistry, event_to_bytes


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


def test_bounded_read_rejects_oversized_history_before_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    course_id = CourseId("course-bounded")
    events = tuple(
        DomainEvent(
            EventId(f"event-{sequence}"),
            course_id,
            sequence,
            "counter.incremented",
            1,
            Actor(PrincipalKind.SERVICE, "test-suite"),
            datetime(2026, 7, 10, 12, tzinfo=UTC) + timedelta(seconds=sequence),
            CorrelationId("correlation-1"),
            {"amount": sequence},
        )
        for sequence in range(1, 4_098)
    )
    assert _append_legacy(store, course_id, 0, events) == 4_097

    import study_agent.adapters.sqlite.event_store as event_store_module

    def fail_decode(_: bytes) -> object:
        raise AssertionError("oversized history must be rejected before decoding")

    monkeypatch.setattr(event_store_module, "event_from_bytes", fail_decode)
    with pytest.raises(ValidationFailure, match="event-count budget"):
        store._read_records_bounded(
            course_id,
            max_events=4_096,
            max_encoded_bytes=32 * 1024 * 1024,
        )


def test_bounded_read_rejects_oversized_encoded_envelope_before_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    course_id = CourseId("course-byte-budget")
    encoded_limit = 32 * 1024 * 1024
    with sqlite3.connect(tmp_path / "events.sqlite3") as connection:
        connection.execute(
            """
            INSERT INTO events (
                course_id, course_sequence, event_id, event_type,
                schema_version, envelope
            ) VALUES (?, ?, ?, ?, ?, zeroblob(?))
            """,
            (
                str(course_id),
                1,
                "event-oversized",
                "counter.incremented",
                1,
                encoded_limit + 1,
            ),
        )

    import study_agent.adapters.sqlite.event_store as event_store_module

    def fail_decode(_: bytes) -> object:
        raise AssertionError("oversized envelope must be rejected before decoding")

    monkeypatch.setattr(event_store_module, "event_from_bytes", fail_decode)
    with pytest.raises(ValidationFailure, match="encoded-byte budget"):
        store._read_records_bounded(
            course_id,
            max_events=4_096,
            max_encoded_bytes=encoded_limit,
        )


def test_bounded_read_accepts_exact_byte_boundary_and_preserves_ordered_bytes(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    course_id = CourseId("course-order")
    first = make_event(course_id, 1)
    second = make_event(course_id, 2)
    _append_legacy(store, course_id, 0, (first, second))
    bounded = store._read_records_bounded(
        course_id,
        max_events=2,
        max_encoded_bytes=len(event_to_bytes(first)) + len(event_to_bytes(second)),
    )
    assert bounded.high_water_sequence == 2
    assert tuple(event.event_id for event in bounded.records) == (
        first.event_id,
        second.event_id,
    )
    assert tuple(event_to_bytes(event) for event in bounded.records) == (
        event_to_bytes(first),
        event_to_bytes(second),
    )


def test_bounded_read_rejects_sqlite_integer_overflow_before_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    def fail_connect() -> sqlite3.Connection:
        raise AssertionError("invalid SQLite integer must be rejected before connecting")

    monkeypatch.setattr(store, "_connect", fail_connect)
    with pytest.raises(ValidationFailure, match="limits"):
        store._read_records_bounded(
            CourseId("course-overflow"),
            max_events=4_096,
            max_encoded_bytes=32 * 1024 * 1024,
            after_sequence=2**63,
        )


def test_bounded_read_maps_recursion_error_to_redacted_validation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    course_id = CourseId("course-recursion")
    _append_legacy(store, course_id, 0, (make_event(course_id, 1),))

    import study_agent.adapters.sqlite.event_store as event_store_module

    def fail_decode(_: bytes) -> object:
        raise RecursionError("secret nested payload")

    monkeypatch.setattr(event_store_module, "event_from_bytes", fail_decode)
    with pytest.raises(ValidationFailure) as error:
        store._read_records_bounded(
            course_id,
            max_events=4_096,
            max_encoded_bytes=32 * 1024 * 1024,
        )
    assert "secret nested payload" not in str(error.value)


def test_bounded_read_uses_one_snapshot_when_a_writer_appends_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(database)
    course_id = CourseId("course-snapshot")
    first = make_event(course_id, 1)
    second = make_event(course_id, 2)
    _append_legacy(store, course_id, 0, (first,))
    started = Event()
    finished = Event()
    errors: list[BaseException] = []
    original_connect = store._connect
    launched = False

    def append_after_preflight() -> None:
        try:
            _append_legacy(store, course_id, 1, (second,))
        except BaseException as error:  # pragma: no cover - diagnostic guard
            errors.append(error)
        finally:
            finished.set()

    def connect_with_writer() -> sqlite3.Connection:
        nonlocal launched
        connection = original_connect()

        def trace(statement: str) -> None:
            nonlocal launched
            if not launched and statement.lstrip().startswith("SELECT COUNT"):
                launched = True
                started.set()
                Thread(target=append_after_preflight, daemon=True).start()

        connection.set_trace_callback(trace)
        return connection

    monkeypatch.setattr(store, "_connect", connect_with_writer)
    bounded = store._read_records_bounded(
        course_id,
        max_events=1,
        max_encoded_bytes=32 * 1024 * 1024,
    )
    assert started.is_set()
    assert finished.wait(5)
    assert errors == []
    assert bounded.high_water_sequence == 1
    assert tuple(event.event_id for event in bounded.records) == (first.event_id,)
    assert tuple(event.event_id for event in store.read(course_id)) == (
        first.event_id,
        second.event_id,
    )
