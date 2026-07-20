from __future__ import annotations

from datetime import UTC, datetime

from study_agent.artifacts.content import AssessmentItemContent
from study_agent.assessments import (
    AssessmentSnapshot,
    AttemptRecord,
    CriterionResult,
    DeterministicGradeProvenance,
    EvidenceDimension,
    EvidenceDisposition,
    FreeResponse,
    GradeContestRecord,
    GradeRecord,
    PresentationRecord,
    ProjectionLearnerEvidenceView,
    RationalScore,
    criterion_evidence_key,
    learner_evidence_from,
    response_fingerprint,
)
from study_agent.domain import (
    ArtifactRevisionId,
    AssessmentFormat,
    AttemptId,
    CourseId,
    CriterionStatus,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    SessionId,
)

COURSE = CourseId("course-evidence")
SESSION = SessionId("session-evidence")
PRESENTATION = PresentationId("presentation-evidence")
ATTEMPT = AttemptId("attempt-evidence")
NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _snapshot(*, contested: bool = False, superseded: bool = False) -> AssessmentSnapshot:
    content = AssessmentItemContent(
        AssessmentFormat.FREE_RESPONSE,
        "Explain the mechanism",
        (),
        "Reference answer",
        ("mechanism", "consequence"),
    )
    response = FreeResponse("Learner answer")
    presentation = PresentationRecord(
        PRESENTATION,
        COURSE,
        SESSION,
        ArtifactRevisionId("revision-evidence"),
        "a" * 64,
        content,
        NOW,
    )
    attempt = AttemptRecord(
        ATTEMPT,
        COURSE,
        SESSION,
        PRESENTATION,
        response,
        response_fingerprint(response),
        None,
        NOW,
    )
    provenance = DeterministicGradeProvenance(
        "exact-policy", "1.0.0", "b" * 64, "c" * 64
    )
    first = GradeRecord(
        GradeId("grade-first"),
        COURSE,
        SESSION,
        ATTEMPT,
        GradeStatus.GRADED,
        (
            CriterionResult("mechanism", CriterionStatus.MET, "supported"),
            CriterionResult("consequence", CriterionStatus.UNCERTAIN, "incomplete"),
        ),
        RationalScore(1, 2),
        provenance,
        GradeLifecycle.SUPERSEDED if superseded else GradeLifecycle.ACTIVE,
        None,
        NOW,
        7,
    )
    grades: tuple[GradeRecord, ...] = (first,)
    if superseded:
        grades += (
            GradeRecord(
                GradeId("grade-second"),
                COURSE,
                SESSION,
                ATTEMPT,
                GradeStatus.GRADED,
                (
                    CriterionResult("mechanism", CriterionStatus.MET, "supported"),
                    CriterionResult("consequence", CriterionStatus.MET, "supported"),
                ),
                RationalScore(1, 1),
                provenance,
                GradeLifecycle.ACTIVE,
                first.id,
                NOW,
                9,
            ),
        )
    active_id = grades[-1].id
    contests = (
        GradeContestRecord(active_id, COURSE, SESSION, "review requested", NOW, 10),
    ) if contested else ()
    return AssessmentSnapshot(COURSE, 10, (presentation,), (attempt,), grades, contests)


def test_effective_ratios_are_exact_and_uncertain_evidence_stays_distinct() -> None:
    result = learner_evidence_from(_snapshot())
    by_dimension = {
        (item.dimension, item.label): item for item in result.estimates
    }

    format_estimate = by_dimension[(EvidenceDimension.FORMAT, "free_response")]
    mechanism = by_dimension[(EvidenceDimension.CRITERION, "mechanism")]
    consequence = by_dimension[(EvidenceDimension.CRITERION, "consequence")]

    assert (format_estimate.numerator, format_estimate.denominator) == (1, 2)
    assert (mechanism.numerator, mechanism.denominator) == (1, 1)
    assert mechanism.evidence[0].disposition is EvidenceDisposition.SUPPORTING
    assert (consequence.numerator, consequence.denominator) == (0, 1)
    assert consequence.evidence[0].disposition is EvidenceDisposition.UNCERTAIN
    assert all(item.through_sequence == 10 for item in result.estimates)


def test_superseded_and_contested_history_remains_ordered_but_not_effective() -> None:
    result = learner_evidence_from(_snapshot(contested=True, superseded=True))
    format_estimate = next(
        item for item in result.estimates if item.dimension is EvidenceDimension.FORMAT
    )

    assert (format_estimate.numerator, format_estimate.denominator) == (0, 0)
    assert tuple(item.event_sequence for item in format_estimate.evidence) == (7, 9, 10)
    assert tuple(item.disposition for item in format_estimate.evidence) == (
        EvidenceDisposition.SUPERSEDED,
        EvidenceDisposition.SUPPORTING,
        EvidenceDisposition.CONTESTED,
    )


def test_criterion_identity_binds_revision_ordinal_and_exact_text() -> None:
    first = criterion_evidence_key("revision-a", 0, "mechanism")

    assert first == criterion_evidence_key("revision-a", 0, "mechanism")
    assert first != criterion_evidence_key("revision-b", 0, "mechanism")
    assert first != criterion_evidence_key("revision-a", 1, "mechanism")


def test_projection_port_exposes_a_separate_course_scoped_snapshot() -> None:
    snapshot = _snapshot()

    class _View:
        def get(self, course_id: CourseId) -> AssessmentSnapshot:
            assert course_id == COURSE
            return snapshot

    view = ProjectionLearnerEvidenceView(_View())

    assert view.get(COURSE) == learner_evidence_from(snapshot)
