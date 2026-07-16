from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from study_agent.artifacts import AssessmentItemContent, StudyArtifactEnvelope
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
    grade_contested_payload,
    grade_recorded_payload,
    item_presented_payload,
    register_assessment_events,
)
from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AssessmentFormat,
    CorrelationId,
    CourseId,
    CriterionStatus,
    DomainEvent,
    GradeId,
    GradeStatus,
    PrincipalKind,
    SessionId,
    StudyArtifactKind,
    assessment_event_id_for,
    attempt_id_for,
    presentation_id_for,
)
from study_agent.state import EventRegistry, Projection, apply_event, canonical_json_bytes

COURSE = CourseId("course")
SESSION = SessionId("session")
REVISION = ArtifactRevisionId("revision")
BATCH = "batch"
NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _content(
    format: AssessmentFormat = AssessmentFormat.SINGLE_CHOICE,
) -> AssessmentItemContent:
    options = ("Alpha", "Beta", "Gamma")
    expected = "Alpha" if format is AssessmentFormat.SINGLE_CHOICE else '["Alpha","Gamma"]'
    return AssessmentItemContent(format, "Which answer?", options, expected, ("correct",))


def _seed(
    *,
    status: ArtifactRevisionStatus = ArtifactRevisionStatus.ACCEPTED,
    kind: StudyArtifactKind = StudyArtifactKind.ASSESSMENT_ITEM,
    content: AssessmentItemContent | None = None,
    stored_content: bytes | None = None,
) -> Projection:
    item = _content() if content is None else content
    encoded = (
        StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, item).to_bytes()
        if stored_content is None
        else stored_content
    )
    return Projection(
        COURSE,
        state={
            "course": {"course_id": str(COURSE)},
            "sessions": {str(SESSION): {"course_id": str(COURSE)}},
            "study_artifacts": {
                "batches": {BATCH: {"course_id": str(COURSE), "session_id": str(SESSION)}},
                "revisions": {
                    str(REVISION): {
                        "batch_id": BATCH,
                        "status": status.value,
                        "kind": kind.value,
                        "content": encoded.decode(),
                    }
                },
            },
        },
    )


def _registry() -> EventRegistry:
    registry = EventRegistry()
    register_assessment_events(registry)
    return registry


def _event(
    sequence: int,
    event_type: str,
    payload: object,
    authority: PrincipalKind,
    *,
    session_id: SessionId = SESSION,
) -> DomainEvent:
    assert isinstance(payload, dict)
    key = payload["idempotency_key"]
    assert isinstance(key, str)
    return DomainEvent(
        assessment_event_id_for(COURSE, session_id, key, event_type),
        COURSE,
        sequence,
        event_type,
        1,
        Actor(authority, "actor"),
        NOW + timedelta(seconds=sequence),
        CorrelationId("correlation"),
        payload,  # type: ignore[arg-type]
        session_id,
    )


def _present(projection: Projection, *, content: AssessmentItemContent | None = None) -> Projection:
    item = _content() if content is None else content
    encoded = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, item).to_bytes()
    payload = dict(
        item_presented_payload(
            REVISION,
            sha256(encoded).hexdigest(),
            item.format,
            item.prompt,
            item.options,
            "present-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    return apply_event(
        projection, _event(1, ITEM_PRESENTED, payload, PrincipalKind.SERVICE), _registry()
    )


def test_presentation_accepts_exact_artifact_and_preserves_prior_projection() -> None:
    before = _seed()
    prior_bytes = before.canonical_bytes()
    after = _present(before)

    assert before.canonical_bytes() == prior_bytes
    records = after.state["assessments"]["presentations"]  # type: ignore[index]
    assert len(records) == 1  # type: ignore[arg-type]
    record = next(iter(records.values()))  # type: ignore[union-attr]
    assert "expected_response" not in record
    assert "evaluation_criteria" not in record


@pytest.mark.parametrize(
    ("status", "kind"),
    (
        (ArtifactRevisionStatus.PROPOSED, StudyArtifactKind.ASSESSMENT_ITEM),
        (ArtifactRevisionStatus.REJECTED, StudyArtifactKind.ASSESSMENT_ITEM),
        (ArtifactRevisionStatus.SUPERSEDED, StudyArtifactKind.ASSESSMENT_ITEM),
        (ArtifactRevisionStatus.ACCEPTED, StudyArtifactKind.STUDY_BRIEF),
    ),
)
def test_presentation_rejects_unaccepted_or_wrong_kind_artifacts(
    status: ArtifactRevisionStatus, kind: StudyArtifactKind
) -> None:
    with pytest.raises(ValueError, match=r"accepted|assessment item"):
        _present(_seed(status=status, kind=kind))


def test_presentation_rejects_missing_revision_fingerprint_drift_and_snapshot_leak() -> None:
    missing = _seed()
    raw_artifacts = dict(missing.state["study_artifacts"])  # type: ignore[arg-type]
    raw_artifacts["revisions"] = {}
    missing = Projection(COURSE, state={**missing.state, "study_artifacts": raw_artifacts})
    with pytest.raises(ValueError):
        _present(missing)

    item = _content()
    encoded = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, item).to_bytes()
    payload = dict(
        item_presented_payload(
            REVISION,
            "0" * 64,
            item.format,
            item.prompt,
            item.options,
            "present-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match="fingerprint"):
        apply_event(_seed(), _event(1, ITEM_PRESENTED, payload, PrincipalKind.SERVICE), _registry())
    assert sha256(encoded).hexdigest() != "0" * 64

    leaked = {**payload, "expected_response": item.expected_response}
    with pytest.raises(ValueError, match="schema"):
        apply_event(_seed(), _event(1, ITEM_PRESENTED, leaked, PrincipalKind.SERVICE), _registry())


def test_attempt_requires_prior_presentation_and_exact_artifact_option_order() -> None:
    presentation = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    payload = dict(
        attempt_recorded_payload(
            presentation,
            SingleChoiceResponse("Alpha"),
            None,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match="presentation"):
        apply_event(_seed(), _event(1, ATTEMPT_RECORDED, payload, PrincipalKind.HUMAN), _registry())

    item = _content(AssessmentFormat.MULTIPLE_CHOICE)
    state = _present(_seed(content=item), content=item)
    reordered = dict(
        attempt_recorded_payload(
            presentation,
            MultipleChoiceResponse(("Gamma", "Alpha")),
            None,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match="option order"):
        apply_event(state, _event(2, ATTEMPT_RECORDED, reordered, PrincipalKind.HUMAN), _registry())
    unknown = dict(
        attempt_recorded_payload(
            presentation,
            MultipleChoiceResponse(("Alpha", "Unknown")),
            None,
            "attempt-2",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match="unknown"):
        apply_event(state, _event(2, ATTEMPT_RECORDED, unknown, PrincipalKind.HUMAN), _registry())


def test_grade_and_contest_require_strict_order_and_preserve_history() -> None:
    registry = _registry()
    state = _present(_seed())
    presentation = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    attempt_payload = dict(
        attempt_recorded_payload(
            presentation,
            SingleChoiceResponse("Alpha"),
            12,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    attempt = attempt_id_for(COURSE, SESSION, presentation, "attempt-1")
    rubric = sha256(canonical_json_bytes({"evaluation_criteria": ("correct",)})).hexdigest()
    grade_payload = dict(
        grade_recorded_payload(
            attempt,
            GradeStatus.GRADED,
            (CriterionResult("correct", CriterionStatus.MET, "Exact"),),
            DeterministicGradeProvenance("exact-choice", "1", "a" * 64, rubric),
            None,
            "grade-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match="attempt"):
        apply_event(
            state, _event(2, GRADE_RECORDED, grade_payload, PrincipalKind.SERVICE), registry
        )

    state = apply_event(
        state, _event(2, ATTEMPT_RECORDED, attempt_payload, PrincipalKind.HUMAN), registry
    )
    grade_id = GradeId(str(grade_payload["grade_id"]))
    contest_payload = dict(grade_contested_payload(grade_id, "Review", "contest-1"))
    with pytest.raises(ValueError, match="grade"):
        apply_event(
            state, _event(3, GRADE_CONTESTED, contest_payload, PrincipalKind.HUMAN), registry
        )

    state = apply_event(
        state, _event(3, GRADE_RECORDED, grade_payload, PrincipalKind.SERVICE), registry
    )
    state = apply_event(
        state, _event(4, GRADE_CONTESTED, contest_payload, PrincipalKind.HUMAN), registry
    )
    assert state.sequence == 4
    assert len(state.state["assessments"]["grades"]) == 1  # type: ignore[index,arg-type]
    assert len(state.state["assessments"]["contests"]) == 1  # type: ignore[index,arg-type]


def test_duplicate_command_and_cross_session_reference_fail_closed() -> None:
    registry = _registry()
    state = _present(_seed())
    item = _content()
    encoded = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, item).to_bytes()
    duplicate = dict(
        item_presented_payload(
            REVISION,
            sha256(encoded).hexdigest(),
            item.format,
            item.prompt,
            item.options,
            "present-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    with pytest.raises(ValueError, match=r"command|exists"):
        apply_event(state, _event(2, ITEM_PRESENTED, duplicate, PrincipalKind.SERVICE), registry)

    other = SessionId("other-session")
    cross = dict(
        item_presented_payload(
            REVISION,
            sha256(encoded).hexdigest(),
            item.format,
            item.prompt,
            item.options,
            "other",
            course_id=COURSE,
            session_id=other,
        )
    )
    with pytest.raises(ValueError, match="session"):
        apply_event(
            _seed(),
            _event(1, ITEM_PRESENTED, cross, PrincipalKind.SERVICE, session_id=other),
            registry,
        )


def test_grade_supersession_requires_active_same_attempt_predecessor() -> None:
    registry = _registry()
    state = _present(_seed())
    presentation = presentation_id_for(COURSE, SESSION, REVISION, "present-1")
    attempt_payload = dict(
        attempt_recorded_payload(
            presentation,
            SingleChoiceResponse("Alpha"),
            None,
            "attempt-1",
            course_id=COURSE,
            session_id=SESSION,
        )
    )
    state = apply_event(
        state, _event(2, ATTEMPT_RECORDED, attempt_payload, PrincipalKind.HUMAN), registry
    )
    attempt = attempt_id_for(COURSE, SESSION, presentation, "attempt-1")
    rubric = sha256(canonical_json_bytes({"evaluation_criteria": ("correct",)})).hexdigest()

    def grade(key: str, predecessor: GradeId | None) -> dict[str, object]:
        return dict(
            grade_recorded_payload(
                attempt,
                GradeStatus.GRADED,
                (CriterionResult("correct", CriterionStatus.MET, key),),
                DeterministicGradeProvenance("exact-choice", "1", "a" * 64, rubric),
                predecessor,
                key,
                course_id=COURSE,
                session_id=SESSION,
            )
        )

    first = grade("grade-1", None)
    state = apply_event(state, _event(3, GRADE_RECORDED, first, PrincipalKind.SERVICE), registry)
    first_id = GradeId(str(first["grade_id"]))
    with pytest.raises(ValueError, match="supersess"):
        apply_event(
            state,
            _event(4, GRADE_RECORDED, grade("grade-2", GradeId("missing")), PrincipalKind.SERVICE),
            registry,
        )
    second = grade("grade-2", first_id)
    state = apply_event(state, _event(4, GRADE_RECORDED, second, PrincipalKind.SERVICE), registry)
    grades = state.state["assessments"]["grades"]  # type: ignore[index]
    assert len(grades) == 2  # type: ignore[arg-type]
    assert grades[str(first_id)]["lifecycle"] == "superseded"  # type: ignore[index]
