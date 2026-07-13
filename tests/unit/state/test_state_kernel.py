from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.state import (
    EventRegistry,
    PayloadValidationError,
    Projection,
    ReducerRegistrationError,
    UnknownEventSchemaError,
    apply_event,
    canonical_json_bytes,
    event_from_bytes,
    event_to_bytes,
)


def event(*, version: int = 1, sequence: int = 1) -> DomainEvent:
    return DomainEvent(
        EventId(f"event-{sequence}"),
        CourseId("course-1"),
        sequence,
        "item.recorded",
        version,
        Actor(PrincipalKind.HUMAN, "local-user"),
        datetime(2026, 7, 10, 12, 30, tzinfo=UTC) + timedelta(minutes=sequence),
        CorrelationId("correlation-1"),
        {"label": "β", "ordinal": sequence},
    )


def decode_item(payload: JsonObject) -> tuple[str, int]:
    label = payload.get("label")
    ordinal = payload.get("ordinal")
    if not isinstance(label, str) or not isinstance(ordinal, int):
        raise ValueError("item payload requires string label and integer ordinal")
    return label, ordinal


def test_canonical_serialization_sorts_keys_and_round_trips_event_envelope() -> None:
    assert canonical_json_bytes({"z": 1, "a": {"two": 2, "one": 1}}) == (
        b'{"a":{"one":1,"two":2},"z":1}'
    )
    original = event()
    encoded = event_to_bytes(original)

    assert event_to_bytes(event_from_bytes(encoded)) == encoded
    assert event_from_bytes(encoded) == original


def test_registry_dispatches_exact_schema_version_and_prevents_duplicate_registration() -> None:
    registry = EventRegistry()

    def v1(
        state: JsonObject, _: DomainEvent, __: tuple[str, int]
    ) -> Mapping[str, JsonValue]:
        return {**state, "dispatched": "v1"}

    def v2(
        state: JsonObject, _: DomainEvent, __: tuple[str, int]
    ) -> Mapping[str, JsonValue]:
        return {**state, "dispatched": "v2"}

    registry.register("item.recorded", 1, decode_item, v1)
    registry.register("item.recorded", 2, decode_item, v2)

    assert apply_event(Projection(CourseId("course-1")), event(version=2), registry).state == {
        "dispatched": "v2"
    }
    with pytest.raises(ReducerRegistrationError):
        registry.register("item.recorded", 1, decode_item, v1)
    with pytest.raises(UnknownEventSchemaError):
        registry.reduce({}, event(version=3))


def test_reducer_receives_immutable_state_and_returns_a_new_projection() -> None:
    registry = EventRegistry()

    def reducer(
        state: JsonObject, _: DomainEvent, payload: tuple[str, int]
    ) -> Mapping[str, JsonValue]:
        with pytest.raises(TypeError):
            state["mutated"] = True  # type: ignore[index]
        return {**state, "last": payload[1]}

    registry.register("item.recorded", 1, decode_item, reducer)
    before = Projection(CourseId("course-1"), state={"stable": True})
    after = apply_event(before, event(), registry)

    assert before.state == {"stable": True}
    assert after.state == {"last": 1, "stable": True}


def test_typed_registration_decodes_payload_before_reduction() -> None:
    @dataclass(frozen=True, slots=True)
    class RecordedItem:
        label: str

    def decode(payload: JsonObject) -> RecordedItem:
        label = payload.get("label")
        if not isinstance(label, str):
            raise ValueError("label must be a string")
        return RecordedItem(label)

    def reducer(
        state: JsonObject, _: DomainEvent, payload: RecordedItem
    ) -> Mapping[str, JsonValue]:
        return {**state, "decoded_label": payload.label}

    registry = EventRegistry()
    registry.register_typed("item.recorded", 1, decode, reducer)
    result = apply_event(Projection(CourseId("course-1")), event(), registry)
    assert result.state["decoded_label"] == "β"

    malformed = DomainEvent(
        EventId("event-malformed"),
        CourseId("course-1"),
        1,
        "item.recorded",
        1,
        Actor(PrincipalKind.HUMAN, "local-user"),
        datetime(2026, 7, 10, 12, 30, tzinfo=UTC),
        CorrelationId("correlation-1"),
        {"label": 3},
    )
    with pytest.raises(PayloadValidationError, match="label must be a string"):
        registry.decode(malformed)
