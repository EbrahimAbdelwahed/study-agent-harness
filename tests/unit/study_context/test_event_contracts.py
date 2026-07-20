from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

import pytest

from study_agent.domain import (
    Actor,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    InteractionId,
    PrincipalKind,
    SessionId,
    StudyStatementInput,
    StudyStatementKind,
    statement_id_for,
    study_context_event_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.state import (
    EventRegistry,
    PayloadValidationError,
    event_from_bytes,
    event_to_bytes,
)
from study_agent.study_context import (
    CONFLICT_RESOLVED,
    STATEMENT_RECORDED,
    register_study_context_events,
)
from study_agent.study_context.events import (
    conflict_resolved_payload,
    statement_recorded_payload,
)

COURSE = CourseId("course-context-codec")
SESSION = SessionId("session-context-codec")
ORIGIN = InteractionId("interaction-human-origin")
NOW = datetime(2026, 7, 14, 9, tzinfo=UTC)


def _record_event(
    *,
    actor: PrincipalKind = PrincipalKind.HUMAN,
    payload: JsonObject | None = None,
    session_id: SessionId = SESSION,
    causation_id: EventId | None = None,
) -> DomainEvent:
    event_id = study_context_event_id_for(COURSE, SESSION, "record-one", "record")
    statement = StudyStatementInput(StudyStatementKind.DEADLINE, date(2026, 9, 8))
    return DomainEvent(
        event_id,
        COURSE,
        4,
        STATEMENT_RECORDED,
        1,
        Actor(actor, "codec-test"),
        NOW,
        CorrelationId("correlation-codec"),
        payload
        or statement_recorded_payload(
            statement_id_for(event_id), ORIGIN, statement, SESSION, "record-one"
        ),
        session_id,
        causation_id,
    )


def _registry() -> EventRegistry:
    registry = EventRegistry()
    register_study_context_events(registry)
    return registry


def test_record_codec_validates_complete_envelope_after_serialization() -> None:
    event = event_from_bytes(event_to_bytes(_record_event()))

    decoded = _registry().decode(event)

    assert decoded.statement_id == statement_id_for(event.event_id)  # type: ignore[attr-defined]
    assert decoded.origin_interaction_id == ORIGIN  # type: ignore[attr-defined]
    assert decoded.statement == StudyStatementInput(  # type: ignore[attr-defined]
        StudyStatementKind.DEADLINE, date(2026, 9, 8)
    )


def test_record_codec_rejects_unknown_payload_fields() -> None:
    valid = _record_event()
    malformed = _record_event(payload=cast(JsonObject, {**valid.payload, "unexpected": True}))

    with pytest.raises(PayloadValidationError, match="payload fields mismatch"):
        _registry().decode(malformed)


@pytest.mark.parametrize(
    "event",
    (
        _record_event(actor=PrincipalKind.MODEL),
        _record_event(session_id=SessionId("another-session")),
    ),
)
def test_record_codec_rejects_untrusted_or_inconsistent_envelopes(
    event: DomainEvent,
) -> None:
    with pytest.raises(PayloadValidationError):
        _registry().decode(event)


def test_record_codec_preserves_typed_causation_for_capability_provenance() -> None:
    event = _record_event(causation_id=EventId("event-capability-command"))

    decoded = _registry().decode(event)

    assert decoded.statement_id == statement_id_for(event.event_id)  # type: ignore[attr-defined]


def test_reducer_rejects_record_with_no_canonical_human_origin() -> None:
    state: JsonObject = {
        "course": {"course_id": str(COURSE)},
        "sessions": {
            str(SESSION): {
                "session_id": str(SESSION),
                "course_id": str(COURSE),
            }
        },
        "session_interactions": {},
    }

    with pytest.raises(ValueError, match="canonical human interaction"):
        _registry().reduce(state, _record_event())


def test_reducer_does_not_preserve_mapping_shaped_projection_corruption() -> None:
    state: JsonObject = {
        "course": {"course_id": str(COURSE)},
        "sessions": {
            str(SESSION): {
                "session_id": str(SESSION),
                "course_id": str(COURSE),
            }
        },
        "session_interactions": {
            str(ORIGIN): {
                "session_id": str(SESSION),
                "kind": "human",
            }
        },
        "study_context": {
            "statements": {
                "statement-corrupt": {
                    "statement_id": "statement-corrupt",
                    "course_id": str(COURSE),
                    "session_id": str(SESSION),
                    "origin_interaction_id": str(ORIGIN),
                    "kind": "deadline",
                    "value": "20260714",
                    "status": "active",
                    "recorded_at": NOW.isoformat(),
                }
            },
            "resolutions": (),
            "commands": {},
        },
    }

    with pytest.raises(ValueError, match="statement value is corrupt"):
        _registry().reduce(state, _record_event())


def test_resolution_codec_rejects_noncanonical_loser_order() -> None:
    event_id = study_context_event_id_for(COURSE, SESSION, "resolve-one", "resolve")
    selected = statement_id_for(
        study_context_event_id_for(COURSE, SESSION, "record-a", "record")
    )
    loser_a = statement_id_for(
        study_context_event_id_for(COURSE, SESSION, "record-z", "record")
    )
    loser_b = statement_id_for(
        study_context_event_id_for(COURSE, SESSION, "record-b", "record")
    )
    losers = tuple(sorted((loser_a, loser_b), key=str, reverse=True))
    payload = conflict_resolved_payload(
        StudyStatementKind.DEADLINE, selected, losers, SESSION, "resolve-one"
    )
    event = DomainEvent(
        event_id,
        COURSE,
        6,
        CONFLICT_RESOLVED,
        1,
        Actor(PrincipalKind.SERVICE, "codec-test"),
        NOW,
        CorrelationId("correlation-codec"),
        payload,
        SESSION,
    )

    with pytest.raises(PayloadValidationError, match="canonically ordered"):
        _registry().decode(event)
