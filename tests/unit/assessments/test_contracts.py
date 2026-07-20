from __future__ import annotations

from dataclasses import fields

import pytest

from study_agent.assessments import (
    DeterministicGradeProvenance,
    FreeResponse,
    LearnerPresentationView,
    MultipleChoiceResponse,
    SingleChoiceResponse,
    ValidatorReceipt,
    VerifiedCapabilityGradeProvenance,
    canonical_multiple_choice,
    response_fingerprint,
)
from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    CourseId,
    PresentationId,
    RunId,
    SessionId,
    attempt_id_for,
    grade_id_for,
    presentation_id_for,
)

FINGERPRINT = "a" * 64


def test_assessment_identities_bind_only_trusted_targets_and_retry_identity() -> None:
    course = CourseId("course")
    session = SessionId("session")
    revision = ArtifactRevisionId("revision")

    presentation = presentation_id_for(course, session, revision, "retry-1")
    attempt = attempt_id_for(course, session, presentation, "retry-2")
    grade = grade_id_for(course, session, attempt, "retry-3")

    assert presentation == presentation_id_for(course, session, revision, "retry-1")
    assert attempt == attempt_id_for(course, session, presentation, "retry-2")
    assert grade == grade_id_for(course, session, attempt, "retry-3")
    assert len({str(presentation), str(attempt), str(grade)}) == 3
    assert presentation != presentation_id_for(course, session, revision, "other-retry")
    assert attempt != attempt_id_for(course, session, PresentationId("other"), "retry-2")
    assert grade != grade_id_for(course, session, AttemptId("other"), "retry-3")


def test_identity_signatures_exclude_time_response_model_and_credentials() -> None:
    import inspect

    assert tuple(inspect.signature(presentation_id_for).parameters) == (
        "course_id",
        "session_id",
        "revision_id",
        "retry_identity",
    )
    assert tuple(inspect.signature(attempt_id_for).parameters) == (
        "course_id",
        "session_id",
        "presentation_id",
        "retry_identity",
    )
    assert tuple(inspect.signature(grade_id_for).parameters) == (
        "course_id",
        "session_id",
        "attempt_id",
        "retry_identity",
    )


def test_response_fingerprints_pin_exact_closed_representation_and_order() -> None:
    single = SingleChoiceResponse("left, not parsed")
    multiple = MultipleChoiceResponse(("left", "right"))

    assert canonical_multiple_choice(multiple.selected_options) == '["left","right"]'
    assert response_fingerprint(single) == response_fingerprint(
        SingleChoiceResponse("left, not parsed")
    )
    assert response_fingerprint(multiple) != response_fingerprint(
        MultipleChoiceResponse(("right", "left"))
    )
    assert response_fingerprint(FreeResponse("left")) != response_fingerprint(
        SingleChoiceResponse("left")
    )
    with pytest.raises(ValueError, match="unique"):
        MultipleChoiceResponse(("left", "left"))


def test_grade_provenance_union_is_closed_and_rejects_secrets_or_failed_validation() -> None:
    deterministic = DeterministicGradeProvenance("exact-choice", "1.0.0", FINGERPRINT, "b" * 64)
    assert not hasattr(deterministic, "model_fingerprint")
    with pytest.raises(ValueError, match="secret"):
        DeterministicGradeProvenance("api_key", "1", FINGERPRINT, FINGERPRINT)
    with pytest.raises(ValueError, match="passed"):
        ValidatorReceipt("rubric", "1", FINGERPRINT, False)

    verified = VerifiedCapabilityGradeProvenance(
        RunId("run"),
        "grade_response",
        "1.0.0",
        FINGERPRINT,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        (ValidatorReceipt("rubric", "1", "f" * 64, True),),
        "0" * 64,
    )
    assert verified.validators[0].passed is True
    assert not hasattr(verified, "provider")
    assert not hasattr(verified, "credentials")


def test_learner_presentation_contract_is_structurally_redacted() -> None:
    names = tuple(item.name for item in fields(LearnerPresentationView))
    assert names == ("presentation_id", "revision_id", "format", "prompt", "options")
    assert not {
        "expected_response",
        "evaluation_criteria",
        "content_fingerprint",
        "provenance",
        "source_commitments",
    }.intersection(names)
