from __future__ import annotations

from datetime import UTC, datetime

import pytest

from study_agent.assessments import (
    ATTEMPT_RECORDED,
    GRADE_CONTESTED,
    GRADE_RECORDED,
    ITEM_PRESENTED,
    CriterionResult,
    DeterministicGradeProvenance,
    MultipleChoiceResponse,
    SingleChoiceResponse,
    attempt_recorded_payload,
    decode_attempt_recorded,
    decode_grade_contested,
    decode_grade_recorded,
    decode_item_presented,
    grade_contested_payload,
    grade_recorded_payload,
    item_presented_payload,
)
from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    AssessmentFormat,
    CorrelationId,
    CourseId,
    CriterionStatus,
    DomainEvent,
    GradeId,
    GradeStatus,
    PrincipalKind,
    SessionId,
    assessment_event_id_for,
    attempt_id_for,
    presentation_id_for,
)
from study_agent.state import canonical_json_bytes

COURSE = CourseId("course")
SESSION = SessionId("session")
REVISION = ArtifactRevisionId("revision")
FP = "a" * 64


def _event(
    event_type: str,
    payload: dict[str, object],
    authority: PrincipalKind,
) -> DomainEvent:
    key = payload["idempotency_key"]
    assert isinstance(key, str)
    return DomainEvent(
        assessment_event_id_for(COURSE, SESSION, key, event_type),
        COURSE,
        1,
        event_type,
        1,
        Actor(authority, "actor"),
        datetime(2026, 7, 16, tzinfo=UTC),
        CorrelationId("correlation"),
        payload,  # type: ignore[arg-type]
        SESSION,
    )


def _presentation_payload() -> dict[str, object]:
    return dict(
        item_presented_payload(
            REVISION,
            FP,
            AssessmentFormat.SINGLE_CHOICE,
            "Prompt?",
            ("A", "B"),
            "present-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )


def test_all_event_payloads_decode_and_reencode_byte_identically() -> None:
    presented = _presentation_payload()
    presentation_id = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    attempted = dict(
        attempt_recorded_payload(
            presentation_id,
            MultipleChoiceResponse(("A", "B")),
            150,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    attempt_id = attempt_id_for(COURSE, SESSION, presentation_id, "attempt-1")
    graded = dict(
        grade_recorded_payload(
            attempt_id,
            GradeStatus.GRADED,
            (CriterionResult("correct", CriterionStatus.MET, "Exact"),),
            DeterministicGradeProvenance("exact-choice", "1", FP, "b" * 64),
            None,
            "grade-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    grade_id = GradeId(str(graded["grade_id"]))
    contested = dict(grade_contested_payload(grade_id, "Please review", "contest-1"))

    cases = (
        (ITEM_PRESENTED, presented, PrincipalKind.SERVICE, decode_item_presented),
        (ATTEMPT_RECORDED, attempted, PrincipalKind.HUMAN, decode_attempt_recorded),
        (GRADE_RECORDED, graded, PrincipalKind.SERVICE, decode_grade_recorded),
        (GRADE_CONTESTED, contested, PrincipalKind.HUMAN, decode_grade_contested),
    )
    for event_type, payload, authority, decoder in cases:
        before = canonical_json_bytes(payload)  # type: ignore[arg-type]
        decoder(_event(event_type, payload, authority))
        assert canonical_json_bytes(payload) == before  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["mastery", "schedule", "learner_model", "credentials"])
def test_codecs_reject_forbidden_state_and_secret_shapes(field: str) -> None:
    payload = _presentation_payload()
    payload[field] = {"secret": "sk-live-example"}
    with pytest.raises(ValueError, match=r"forbidden|schema"):
        decode_item_presented(_event(ITEM_PRESENTED, payload, PrincipalKind.SERVICE))


def test_codecs_reject_missing_extra_wrong_authority_and_fingerprint_drift() -> None:
    payload = _presentation_payload()
    missing = dict(payload)
    missing.pop("prompt")
    extra = {**payload, "unrelated": "value"}
    malformed = {**payload, "content_fingerprint": "A" * 64}
    command_drift = {**payload, "prompt": "changed"}

    for invalid in (missing, extra, malformed, command_drift):
        with pytest.raises(ValueError):
            decode_item_presented(_event(ITEM_PRESENTED, invalid, PrincipalKind.SERVICE))
    with pytest.raises(ValueError, match="SERVICE"):
        decode_item_presented(_event(ITEM_PRESENTED, payload, PrincipalKind.MODEL))


@pytest.mark.parametrize(
    "response",
    (
        {"kind": "multiple_choice", "value": "A,B"},
        {"kind": "multiple_choice", "value": '["A","A"]'},
        {"kind": "multiple_choice", "value": '["B", "A"]'},
        {"kind": "fuzzy", "value": "A"},
        {"kind": "single_choice", "value": "A", "confidence": 1},
    ),
)
def test_attempt_codec_rejects_ambiguous_or_malformed_response_unions(
    response: dict[str, object],
) -> None:
    presentation_id = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    payload = dict(
        attempt_recorded_payload(
            presentation_id,
            SingleChoiceResponse("A"),
            None,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    payload["response"] = response
    with pytest.raises(ValueError):
        decode_attempt_recorded(_event(ATTEMPT_RECORDED, payload, PrincipalKind.HUMAN))


def test_grade_provenance_codec_forbids_cross_union_and_failed_validator_fields() -> None:
    presentation_id = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    attempt_id = attempt_id_for(COURSE, SESSION, presentation_id, "attempt-1")
    payload = dict(
        grade_recorded_payload(
            attempt_id,
            GradeStatus.GRADED,
            (CriterionResult("correct", CriterionStatus.MET, "Exact"),),
            DeterministicGradeProvenance("exact-choice", "1", FP, "b" * 64),
            None,
            "grade-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    provenance = dict(payload["provenance"])  # type: ignore[arg-type]
    provenance["model_fingerprint"] = "c" * 64
    payload["provenance"] = provenance
    with pytest.raises(ValueError, match="exact schema"):
        decode_grade_recorded(_event(GRADE_RECORDED, payload, PrincipalKind.SERVICE))
