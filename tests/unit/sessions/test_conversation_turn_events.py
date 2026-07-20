from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from study_agent.domain import (
    Actor,
    AssistantTurnRecord,
    AssistantTurnStatus,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    InteractionId,
    InteractionKind,
    PrincipalKind,
    RunId,
    SessionId,
    VerifiedRunOutputRef,
    assistant_interaction_id_for,
    session_turn_event_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.sessions import (
    SESSION_ASSISTANT_TURN_RECORDED,
    SESSION_INTERACTION_RECORDED,
    SESSION_STARTED,
    assistant_turn_recorded_payload,
    interaction_recorded_payload,
    register_session_events,
    session_started_payload,
)
from study_agent.sessions.events import (
    assistant_turn_command_fingerprint,
    decode_assistant_turn_recorded,
    tutor_message_output_fingerprint,
)
from study_agent.state import (
    EventRegistry,
    PayloadValidationError,
    Projection,
    apply_event,
    canonical_json_bytes,
)

NOW = datetime(2026, 7, 14, 8, tzinfo=UTC)
COURSE = CourseId("course-conversation")
SESSION = SessionId("session-conversation")


def _event(
    sequence: int,
    event_type: str,
    payload: JsonObject,
    *,
    session_id: SessionId | None = SESSION,
) -> DomainEvent:
    return DomainEvent(
        EventId(f"event-{sequence}"),
        COURSE,
        sequence,
        event_type,
        1,
        Actor(PrincipalKind.SERVICE, "test-service"),
        NOW + timedelta(seconds=sequence),
        CorrelationId("conversation-test"),
        payload,
        session_id,
    )


def _turn(
    *,
    run_id: str = "run-1",
    key: str = "assistant-key-1",
    reply: InteractionId | None = None,
    sequence: int = 3,
) -> AssistantTurnRecord:
    status = AssistantTurnStatus.COMPLETED
    content = "Let us start with the anatomy objective."
    run = RunId(run_id)
    output = VerifiedRunOutputRef(
        run,
        tutor_message_output_fingerprint(status, content, reply),
    )
    return AssistantTurnRecord(
        assistant_interaction_id_for(COURSE, SESSION, run, key),
        SESSION,
        NOW + timedelta(seconds=sequence),
        status,
        content,
        reply,
        output,
        key,
        assistant_turn_command_fingerprint(status, content, reply, output),
        session_turn_event_id_for(COURSE, SESSION, key, SESSION_ASSISTANT_TURN_RECORDED),
        sequence,
    )


def _registry() -> EventRegistry:
    registry = EventRegistry()
    register_session_events(registry)
    return registry


def _turn_event(record: AssistantTurnRecord) -> DomainEvent:
    return DomainEvent(
        record.event_id,
        COURSE,
        record.course_sequence,
        SESSION_ASSISTANT_TURN_RECORDED,
        1,
        Actor(PrincipalKind.SERVICE, "test-service"),
        record.occurred_at,
        CorrelationId("conversation-test"),
        assistant_turn_recorded_payload(record),
        SESSION,
    )


def _started(registry: EventRegistry) -> Projection:
    return apply_event(
        Projection(COURSE),
        _event(1, SESSION_STARTED, session_started_payload(SESSION)),
        registry,
    )


def test_assistant_turn_codec_requires_exact_payload_and_session_envelope() -> None:
    record = _turn(sequence=2)
    decoded = decode_assistant_turn_recorded(_turn_event(record))
    assert decoded.record == record

    extra = dict(assistant_turn_recorded_payload(record))
    extra["host_status"] = "completed"
    with pytest.raises(ValueError, match="fields mismatch"):
        decode_assistant_turn_recorded(
            DomainEvent(
                record.event_id,
                COURSE,
                2,
                SESSION_ASSISTANT_TURN_RECORDED,
                1,
                Actor(PrincipalKind.SERVICE, "test-service"),
                record.occurred_at,
                CorrelationId("conversation-test"),
                cast(JsonObject, extra),
                SESSION,
            )
        )
    with pytest.raises(ValueError, match=r"event\.session_id"):
        decode_assistant_turn_recorded(
            _event(
                2,
                SESSION_ASSISTANT_TURN_RECORDED,
                assistant_turn_recorded_payload(record),
                session_id=None,
            )
        )
    with pytest.raises(ValueError, match="command identity"):
        decode_assistant_turn_recorded(
            _event(
                2,
                SESSION_ASSISTANT_TURN_RECORDED,
                assistant_turn_recorded_payload(record),
                session_id=SessionId("other-session"),
            )
        )


def test_assistant_turn_codec_rejects_tampered_status_fingerprint_and_output_key() -> None:
    payload = assistant_turn_recorded_payload(_turn(sequence=2))
    for mutate, match in (
        (lambda value: value.update(status="cancelled"), "unsupported"),
        (
            lambda value: cast(dict[str, object], value["output"]).update(
                output_key="arbitrary"
            ),
            "tutor_message",
        ),
        (lambda value: value.update(command_fingerprint="c" * 64), "fingerprint"),
    ):
        candidate: dict[str, JsonValue] = dict(payload)
        candidate["output"] = dict(cast(Mapping[str, JsonValue], payload["output"]))
        mutate(candidate)
        with pytest.raises(ValueError, match=match):
            decode_assistant_turn_recorded(
                DomainEvent(
                    _turn(sequence=2).event_id,
                    COURSE,
                    2,
                    SESSION_ASSISTANT_TURN_RECORDED,
                    1,
                    Actor(PrincipalKind.SERVICE, "test-service"),
                    NOW + timedelta(seconds=2),
                    CorrelationId("conversation-test"),
                    candidate,
                    SESSION,
                )
            )


def test_reducer_fails_closed_for_reply_and_run_relationships() -> None:
    registry = _registry()
    projection = _started(registry)
    projection = apply_event(
        projection,
        _event(
            2,
            SESSION_INTERACTION_RECORDED,
            interaction_recorded_payload(
                InteractionId("learner-1"), InteractionKind.HUMAN, "I study anatomy."
            ),
        ),
        registry,
    )
    first = _turn(reply=InteractionId("learner-1"))
    projection = apply_event(
        projection,
        _turn_event(first),
        registry,
    )
    duplicate_run = _turn(
        run_id="run-1", key="assistant-key-2", sequence=4
    )
    with pytest.raises(ValueError, match="run id already belongs"):
        apply_event(
            projection,
            _turn_event(duplicate_run),
            registry,
        )
    orphan_reply = _turn(
        run_id="run-3",
        key="assistant-key-3",
        reply=InteractionId("missing"),
        sequence=4,
    )
    with pytest.raises(ValueError, match="reply target"):
        apply_event(
            projection,
            _turn_event(orphan_reply),
            registry,
        )


def test_old_only_projection_bytes_are_unchanged_and_new_state_is_additive() -> None:
    registry = _registry()
    projection = _started(registry)
    projection = apply_event(
        projection,
        _event(
            2,
            SESSION_INTERACTION_RECORDED,
            interaction_recorded_payload(
                InteractionId("learner-1"), InteractionKind.HUMAN, "My exam is oral."
            ),
        ),
        registry,
    )
    old_bytes = canonical_json_bytes(projection.state)
    assert "session_assistant_turns" not in projection.state
    rebuilt = Projection(COURSE)
    for event in (
        _event(1, SESSION_STARTED, session_started_payload(SESSION)),
        _event(
            2,
            SESSION_INTERACTION_RECORDED,
            interaction_recorded_payload(
                InteractionId("learner-1"), InteractionKind.HUMAN, "My exam is oral."
            ),
        ),
    ):
        rebuilt = apply_event(rebuilt, event, registry)
    assert canonical_json_bytes(rebuilt.state) == old_bytes

    mixed = apply_event(
        rebuilt,
        _turn_event(_turn(reply=InteractionId("learner-1"))),
        registry,
    )
    assert set(mixed.state) == {*set(rebuilt.state), "session_assistant_turns"}


def test_registry_wraps_invalid_assistant_payload_as_payload_validation_error() -> None:
    registry = _registry()
    with pytest.raises(PayloadValidationError):
        registry.decode(
            _event(
                1,
                SESSION_ASSISTANT_TURN_RECORDED,
                cast(JsonObject, {"status": "completed"}),
            )
        )
