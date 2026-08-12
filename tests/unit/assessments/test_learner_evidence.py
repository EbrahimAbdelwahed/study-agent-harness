from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from study_agent.artifacts.content import AssessmentItemContent, StudyArtifactEnvelope
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
from study_agent.assessments.evidence import ProjectionLearningEvidenceView
from study_agent.domain import (
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AssessmentFormat,
    AttemptId,
    ChunkId,
    CourseId,
    CriterionStatus,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    RevisionId,
    SessionId,
    SourceId,
    StudyArtifactKind,
)
from study_agent.domain.provenance import SourceCommitment

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


def test_projection_learning_evidence_joins_accepted_artifact_provenance() -> None:
    assessment = _snapshot()
    presentation = assessment.presentations[0]
    envelope = StudyArtifactEnvelope(
        StudyArtifactKind.ASSESSMENT_ITEM,
        presentation.content,
    )
    presentation = replace(
        presentation, content_fingerprint=sha256(envelope.to_bytes()).hexdigest()
    )
    assessment = replace(assessment, presentations=(presentation,))
    commitment = SourceCommitment(
        SourceId("source"), RevisionId("source-revision"), ChunkId("chunk"), 0, 10
    )
    revision = SimpleNamespace(
        id=presentation.revision_id,
        status=ArtifactRevisionStatus.ACCEPTED,
        content=envelope,
        provenance=SimpleNamespace(source_commitments=(commitment,)),
    )

    class _Artifacts:
        def get(self, course_id: CourseId) -> object:
            return SimpleNamespace(
                course_id=course_id,
                sequence=assessment.sequence,
                revision=lambda requested: revision,
            )

    result = ProjectionLearningEvidenceView(
        type("Assessments", (), {"get": lambda _, course_id: assessment})(), _Artifacts()
    ).get(COURSE)

    record = result.records[0]
    assert record.source_commitments == (commitment,)
    assert record.content_fingerprint == sha256(envelope.to_bytes()).hexdigest()
    assert record.grading_policy_id == "exact-policy"
    assert record.assistance is None
    assert record.confidence_bps is None


def test_projection_learning_evidence_fails_closed_on_unaccepted_or_divergent_artifact() -> None:
    assessment = _snapshot()
    envelope = StudyArtifactEnvelope(
        StudyArtifactKind.ASSESSMENT_ITEM,
        assessment.presentations[0].content,
    )
    assessment = replace(
        assessment,
        presentations=(
            replace(
                assessment.presentations[0],
                content_fingerprint=sha256(envelope.to_bytes()).hexdigest(),
            ),
        ),
    )
    revision = SimpleNamespace(
        id=assessment.presentations[0].revision_id,
        status=ArtifactRevisionStatus.PROPOSED,
        content=envelope,
        provenance=SimpleNamespace(
            source_commitments=(
                SourceCommitment(SourceId("source"), RevisionId("rev"), ChunkId("chunk"), 0, 10),
            )
        ),
    )

    class _Artifacts:
        def __init__(self, sequence: int) -> None:
            self.sequence = sequence

        def get(self, course_id: CourseId) -> object:
            return SimpleNamespace(
                course_id=course_id,
                sequence=self.sequence,
                revision=lambda requested: revision,
            )

    assessment_view = type("Assessments", (), {"get": lambda _, course_id: assessment})()
    with pytest.raises(ValueError, match="accepted"):
        ProjectionLearningEvidenceView(assessment_view, _Artifacts(assessment.sequence)).get(COURSE)
    revision.status = ArtifactRevisionStatus.ACCEPTED
    with pytest.raises(ValueError, match="divergent"):
        ProjectionLearningEvidenceView(
            assessment_view, _Artifacts(assessment.sequence - 1)
        ).get(COURSE)
