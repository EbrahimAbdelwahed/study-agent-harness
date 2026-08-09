from datetime import UTC, datetime

import pytest

from study_agent.api.events import Actor, EventEnvelope, PrincipalKind
from study_agent.domain.errors import ValidationFailure


def envelope(**overrides: object) -> EventEnvelope:
    values: dict[str, object] = {
        "event_id": "event-1",
        "event_type": "study.card.created",
        "schema_version": 1,
        "stream_id": "course-1",
        "stream_sequence": 1,
        "occurred_at": datetime(2026, 8, 9, 12, tzinfo=UTC),
        "correlation_id": "corr-1",
        "actor": Actor(PrincipalKind.SERVICE, "host"),
        "payload": {"nested": {"value": 1}, "items": [True]},
        "causation_id": None,
    }
    values.update(overrides)
    return EventEnvelope(**values)  # type: ignore[arg-type]


def test_envelope_is_canonical_and_deeply_frozen() -> None:
    event = envelope()
    assert event.canonical_bytes() == EventEnvelope.from_bytes(
        event.canonical_bytes()
    ).canonical_bytes()
    with pytest.raises(TypeError):
        event.payload["nested"] = {}  # type: ignore[index]


@pytest.mark.parametrize(
    "field,value",
    [("event_type", "Study.Card"), ("schema_version", 0), ("stream_sequence", 0)],
)
def test_envelope_rejects_invalid_schema_metadata(field: str, value: object) -> None:
    with pytest.raises(ValidationFailure):
        envelope(**{field: value})


def test_envelope_rejects_unsafe_json() -> None:
    with pytest.raises(ValidationFailure):
        envelope(payload={"bytes": b"secret"})
    with pytest.raises(ValidationFailure):
        envelope(payload={"number": float("nan")})


def test_envelope_rejects_self_causation() -> None:
    with pytest.raises(ValidationFailure):
        envelope(causation_id="event-1")
