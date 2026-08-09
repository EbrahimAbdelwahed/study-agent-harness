from datetime import UTC, datetime

import pytest

from study_agent.domain.errors import ConflictFailure, ValidationFailure
from study_agent.domain.events import Actor, EventEnvelope, PrincipalKind
from study_agent.events.upcasting import EventUpcasterRegistry


def event(version: int = 1, payload: dict[str, object] | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id="event-1",
        event_type="study.card.created",
        schema_version=version,
        stream_id="course-1",
        stream_sequence=2,
        occurred_at=datetime(2026, 8, 9, tzinfo=UTC),
        correlation_id="corr-1",
        causation_id="event-0",
        actor=Actor(PrincipalKind.SERVICE, "host"),
        payload=payload or {"front": "q"},
    )


def test_adjacent_upcast_preserves_identity_and_is_deterministic() -> None:
    registry = EventUpcasterRegistry()
    registry.register("study.card.created", 1, lambda payload: {**payload, "back": "a"})
    upgraded = registry.upcast(event())
    assert upgraded.schema_version == 2
    assert upgraded.payload == {"front": "q", "back": "a"}
    assert str(upgraded.event_id) == "event-1"
    assert str(upgraded.causation_id) == "event-0"
    assert upgraded.canonical_bytes() == registry.upcast(event()).canonical_bytes()


def test_unknown_or_malformed_upcast_fails_closed() -> None:
    registry = EventUpcasterRegistry()
    with pytest.raises(ValidationFailure):
        registry.upcast(event())
    registry.register("study.card.created", 1, lambda payload: [payload])  # type: ignore[arg-type]
    with pytest.raises(ValidationFailure):
        registry.upcast(event())


def test_duplicate_and_late_registration_are_typed_failures() -> None:
    registry = EventUpcasterRegistry()
    registry.register("study.card.created", 1, lambda payload: payload)
    with pytest.raises(ConflictFailure):
        registry.register("study.card.created", 1, lambda payload: payload)
    registry.close()
    with pytest.raises(ValidationFailure):
        registry.register("study.card.created", 2, lambda payload: payload)
