from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from study_agent.domain import (
    Actor,
    AnswerId,
    AnswerProvenance,
    AnswerStatus,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    GroundedAnswer,
    InteractionId,
    InteractionKind,
    PrincipalKind,
    PromptProvenance,
    RetrievalProvenance,
    RunId,
    SessionId,
    ValidatorProvenance,
    VersionPins,
    answer_id_for,
    assistant_interaction_id_for,
    question_interaction_id_for,
    session_event_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.session import AnswerRecord
from study_agent.sessions import (
    SESSION_ANSWER_RECORDED,
    SESSION_CONTINUATION_SUMMARY_UPDATED,
    SESSION_ENDED,
    SESSION_INTERACTION_RECORDED,
    SESSION_RESUMED,
    SESSION_STARTED,
    SESSION_SUSPENDED,
    answer_recorded_payload,
    build_continuation_summary,
    interaction_recorded_payload,
    lifecycle_payload,
    register_session_events,
    session_started_payload,
    summary_payload,
)
from study_agent.sessions.projection import _decode_answer, _decode_interaction
from study_agent.state import EventRegistry, PayloadValidationError, Projection, apply_event

NOW = datetime(2026, 7, 11, 12, tzinfo=UTC)
COURSE = CourseId("course-1")
SESSION = SessionId("session-1")
HASH = "a" * 64


def _event(
    sequence: int,
    event_type: str,
    payload: JsonObject,
    *,
    session_id: SessionId = SESSION,
    at: datetime | None = None,
) -> DomainEvent:
    return DomainEvent(
        EventId(f"event-{sequence}"),
        COURSE,
        sequence,
        event_type,
        1,
        Actor(PrincipalKind.SERVICE, "test-service"),
        at or NOW + timedelta(seconds=sequence),
        CorrelationId("correlation-1"),
        payload,
        session_id,
    )


def _insufficient_answer() -> GroundedAnswer:
    provenance = AnswerProvenance(
        (),
        PromptProvenance("grounded_answer", "1.0.0"),
        None,
        RetrievalProvenance("sqlite_fts5", "1", HASH, "index-1", "b" * 64),
        (
            ValidatorProvenance(
                "evidence_sufficiency", "1", True, "terminate", "c" * 64
            ),
        ),
        VersionPins(
            "grounded_answer@1.0.0",
            "grounded_answer_flow@1.0.0",
            "grounded_answer@1.0.0",
            None,
            "session@1",
            "tools@1",
        ),
        RunId("run-1"),
    )
    return GroundedAnswer(
        AnswerStatus.INSUFFICIENT_EVIDENCE,
        (),
        "The supplied sources do not contain enough evidence.",
        provenance,
    )


def _answer_record() -> AnswerRecord:
    return AnswerRecord(
        AnswerId("answer-1"),
        InteractionId("assistant-1"),
        InteractionId("question-1"),
        RunId("run-1"),
        "retry-1",
        "d" * 64,
        _insufficient_answer(),
    )


def _registry() -> EventRegistry:
    registry = EventRegistry()
    register_session_events(registry)
    return registry


def _through_answer() -> tuple[Projection, EventRegistry]:
    registry = _registry()
    projection = Projection(COURSE, state=cast(JsonObject, {"sources": {"kept": True}}))
    events = (
        _event(1, SESSION_STARTED, session_started_payload(SESSION)),
        _event(
            2,
            SESSION_INTERACTION_RECORDED,
            interaction_recorded_payload(
                InteractionId("question-1"), InteractionKind.HUMAN, "What is absent?"
            ),
        ),
        _event(3, SESSION_ANSWER_RECORDED, answer_recorded_payload(_answer_record())),
    )
    for event in events:
        projection = apply_event(projection, event, registry)
    return projection, registry


def test_codecs_reject_unknown_fields_and_cross_session_envelopes() -> None:
    registry = _registry()
    extra = cast(JsonObject, {"session_id": str(SESSION), "unexpected": True})
    with pytest.raises(PayloadValidationError, match="fields mismatch"):
        registry.decode(_event(1, SESSION_STARTED, extra))

    with pytest.raises(PayloadValidationError, match="must match"):
        registry.decode(
            _event(
                1,
                SESSION_STARTED,
                session_started_payload(SessionId("other")),
            )
        )


def test_mixed_stream_reducer_preserves_source_state_and_rejects_duplicates() -> None:
    projection, registry = _through_answer()
    assert projection.state["sources"] == {"kept": True}
    duplicate = _event(
        4,
        SESSION_INTERACTION_RECORDED,
        interaction_recorded_payload(
            InteractionId("question-1"), InteractionKind.NOTE, "duplicate"
        ),
    )
    with pytest.raises(ValueError, match="already exists"):
        apply_event(projection, duplicate, registry)


def test_summary_must_equal_canonical_history_and_advance_monotonically() -> None:
    projection, registry = _through_answer()
    interactions_raw = cast(JsonObject, projection.state["session_interactions"])
    answers_raw = cast(JsonObject, projection.state["session_answers"])
    interactions = tuple(
        _decode_interaction(interaction_id, cast(JsonObject, raw))
        for interaction_id, raw in interactions_raw.items()
    )
    answers = {
        answer_id: _decode_answer(answer_id, cast(JsonObject, raw))
        for answer_id, raw in answers_raw.items()
    }
    summary = build_continuation_summary(interactions, answers)
    projection = apply_event(
        projection,
        _event(4, SESSION_CONTINUATION_SUMMARY_UPDATED, summary_payload(summary)),
        registry,
    )
    assert projection.state["sources"] == {"kept": True}
    with pytest.raises(ValueError, match="advance monotonically"):
        apply_event(
            projection,
            _event(5, SESSION_CONTINUATION_SUMMARY_UPDATED, summary_payload(summary)),
            registry,
        )


def test_lifecycle_is_strict_and_ended_session_is_terminal() -> None:
    projection, registry = _through_answer()
    projection = apply_event(
        projection, _event(4, SESSION_SUSPENDED, lifecycle_payload()), registry
    )
    projection = apply_event(
        projection, _event(5, SESSION_RESUMED, lifecycle_payload()), registry
    )
    projection = apply_event(
        projection, _event(6, SESSION_ENDED, lifecycle_payload()), registry
    )
    with pytest.raises(ValueError, match="active"):
        apply_event(
            projection,
            _event(
                7,
                SESSION_INTERACTION_RECORDED,
                interaction_recorded_payload(
                    InteractionId("note-after-end"), InteractionKind.NOTE, "late"
                ),
            ),
            registry,
        )


def test_answer_codec_rejects_tampered_duplicate_provenance() -> None:
    payload = dict(answer_recorded_payload(_answer_record()))
    provenance = dict(cast(JsonObject, payload["provenance"]))
    provenance["playbook_run_id"] = "different-run"
    payload["provenance"] = provenance
    with pytest.raises(PayloadValidationError, match="exactly match"):
        _registry().decode(
            _event(3, SESSION_ANSWER_RECORDED, cast(JsonObject, payload))
        )


def test_answer_codec_rejects_failed_insufficient_validator_even_when_copies_match() -> None:
    payload = dict(answer_recorded_payload(_answer_record()))
    for field in ("answer", "provenance"):
        if field == "answer":
            answer = dict(cast(JsonObject, payload[field]))
            provenance = dict(cast(JsonObject, answer["provenance"]))
        else:
            provenance = dict(cast(JsonObject, payload[field]))
        validators = list(cast(tuple[JsonObject, ...], provenance["validators"]))
        receipt = dict(validators[0])
        receipt["passed"] = False
        validators[0] = receipt
        provenance["validators"] = tuple(validators)
        if field == "answer":
            answer["provenance"] = provenance
            payload[field] = answer
        else:
            payload[field] = provenance

    with pytest.raises(PayloadValidationError, match="failed validators"):
        _registry().decode(
            _event(3, SESSION_ANSWER_RECORDED, cast(JsonObject, payload))
        )


def test_insufficient_answer_rejects_fabricated_model_provenance() -> None:
    provenance = _insufficient_answer().provenance
    assert provenance.model is None
    with pytest.raises(ValueError, match="model adapter pin"):
        AnswerProvenance(
            provenance.source_commitments,
            provenance.prompt,
            None,
            provenance.retrieval,
            provenance.validators,
            VersionPins(
                provenance.pins.skill,
                provenance.pins.playbook,
                provenance.pins.prompt,
                "fake@1",
                provenance.pins.state_contract,
                provenance.pins.tool_behavior,
            ),
            provenance.playbook_run_id,
        )


def test_retry_identifiers_are_deterministic_and_purpose_separated() -> None:
    inputs = (COURSE, SESSION, RunId("run-1"), "retry-1")
    answer_id = answer_id_for(*inputs)
    assert answer_id == answer_id_for(*inputs)
    assert str(answer_id).startswith("answer-sha256:")
    assert question_interaction_id_for(*inputs) != assistant_interaction_id_for(*inputs)
    assert session_event_id_for(*inputs, SESSION_ANSWER_RECORDED) != session_event_id_for(
        *inputs, SESSION_CONTINUATION_SUMMARY_UPDATED
    )
