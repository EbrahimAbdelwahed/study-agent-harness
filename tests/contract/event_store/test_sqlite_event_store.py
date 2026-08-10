from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

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
