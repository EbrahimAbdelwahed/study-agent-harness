"""Pure learner-evidence projection over canonical assessment history."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import TYPE_CHECKING

from study_agent.domain import (
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AttemptId,
    CourseId,
    CriterionStatus,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    SessionId,
)
from study_agent.domain._validation import require_text
from study_agent.domain.provenance import SourceCommitment
from study_agent.ports.artifact import ArtifactViewPort
from study_agent.ports.assessment import AssessmentViewPort
from study_agent.state import canonical_json_bytes

from .contracts import (
    AssessmentSnapshot,
    AttemptRecord,
    CriterionResult,
    DeterministicGradeProvenance,
    GradeRecord,
    PresentationRecord,
    RationalScore,
)

if TYPE_CHECKING:
    from study_agent.artifacts.contracts import ArtifactRevisionRecord


class EvidenceDimension(StrEnum):
    FORMAT = "format"
    CRITERION = "criterion"


class EvidenceDisposition(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    UNCERTAIN = "uncertain"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class LearnerEvidenceReference:
    grade_id: GradeId
    event_sequence: int
    disposition: EvidenceDisposition
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if not isinstance(self.grade_id, GradeId):
            raise TypeError("learner evidence requires GradeId")
        if type(self.event_sequence) is not int or self.event_sequence <= 0:
            raise ValueError("learner evidence sequence must be positive")
        if not isinstance(self.disposition, EvidenceDisposition):
            raise TypeError("learner evidence disposition is invalid")
        if (
            type(self.numerator) is not int
            or type(self.denominator) is not int
            or self.denominator < 0
            or not 0 <= self.numerator <= self.denominator
        ):
            raise ValueError("learner evidence ratio contribution is invalid")


@dataclass(frozen=True, slots=True)
class LearnerEvidenceEstimate:
    dimension: EvidenceDimension
    key: str
    label: str
    numerator: int
    denominator: int
    through_sequence: int
    evidence: tuple[LearnerEvidenceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, EvidenceDimension):
            raise TypeError("learner evidence dimension is invalid")
        if not self.key or not self.label:
            raise ValueError("learner evidence key and label are required")
        if (
            type(self.numerator) is not int
            or type(self.denominator) is not int
            or not 0 <= self.numerator <= self.denominator
        ):
            raise ValueError("learner evidence estimate ratio is invalid")
        if type(self.through_sequence) is not int or self.through_sequence < 0:
            raise ValueError("learner evidence through_sequence is invalid")
        values = tuple(self.evidence)
        if tuple(item.event_sequence for item in values) != tuple(
            sorted(item.event_sequence for item in values)
        ):
            raise ValueError("learner evidence must be in canonical event order")
        if (self.numerator, self.denominator) != (
            sum(item.numerator for item in values),
            sum(item.denominator for item in values),
        ):
            raise ValueError("learner evidence estimate differs from its references")
        object.__setattr__(self, "evidence", values)


@dataclass(frozen=True, slots=True)
class LearnerEvidenceSnapshot:
    course_id: CourseId
    through_sequence: int
    estimates: tuple[LearnerEvidenceEstimate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.course_id, CourseId):
            raise TypeError("learner evidence snapshot requires CourseId")
        if type(self.through_sequence) is not int or self.through_sequence < 0:
            raise ValueError("learner evidence snapshot sequence is invalid")
        values = tuple(self.estimates)
        identities = tuple((item.dimension, item.key) for item in values)
        if identities != tuple(sorted(identities, key=lambda item: (item[0].value, item[1]))):
            raise ValueError("learner evidence estimates are not canonically ordered")
        if len(set(identities)) != len(identities):
            raise ValueError("learner evidence estimates are duplicated")
        object.__setattr__(self, "estimates", values)


class ProjectionLearnerEvidenceView:
    def __init__(self, assessments: AssessmentViewPort) -> None:
        self._assessments = assessments

    def get(self, course_id: CourseId) -> LearnerEvidenceSnapshot:
        return learner_evidence_from(self._assessments.get(course_id))


@dataclass(frozen=True, slots=True)
class LearningEvidenceRecord:
    """One assessment observation joined to its accepted artifact provenance.

    This is deliberately a fact projection, not a mastery estimate.  The
    current event schema does not observe assistance or confidence, so the
    projection emits ``None`` for both fields and never infers a value.
    """

    course_id: CourseId
    session_id: SessionId
    revision_id: ArtifactRevisionId
    presentation_id: PresentationId
    attempt_id: AttemptId
    grade_id: GradeId
    source_commitments: tuple[SourceCommitment, ...]
    content_fingerprint: str
    grading_policy_id: str
    grading_policy_version: str
    grading_policy_fingerprint: str
    rubric_fingerprint: str
    score: RationalScore
    grade_status: GradeStatus
    grade_lifecycle: GradeLifecycle
    criterion_results: tuple[CriterionResult, ...]
    assistance: str | None
    confidence_bps: int | None
    event_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.course_id, CourseId) or not isinstance(self.session_id, SessionId):
            raise TypeError("learning evidence scope is invalid")
        if not isinstance(self.revision_id, ArtifactRevisionId):
            raise TypeError("learning evidence revision is invalid")
        if not isinstance(self.presentation_id, PresentationId) or not isinstance(
            self.attempt_id, AttemptId
        ) or not isinstance(self.grade_id, GradeId):
            raise TypeError("learning evidence identities are invalid")
        if not isinstance(self.score, RationalScore):
            raise TypeError("learning evidence score is invalid")
        if not isinstance(self.grade_status, GradeStatus) or not isinstance(
            self.grade_lifecycle, GradeLifecycle
        ):
            raise TypeError("learning evidence grade state is invalid")
        criteria = tuple(self.criterion_results)
        if not all(isinstance(item, CriterionResult) for item in criteria):
            raise TypeError("learning evidence criteria are invalid")
        object.__setattr__(self, "criterion_results", criteria)
        commitments = tuple(self.source_commitments)
        if not commitments or not all(isinstance(item, SourceCommitment) for item in commitments):
            raise ValueError("learning evidence requires accepted source commitments")
        object.__setattr__(self, "source_commitments", commitments)
        _fingerprint(self.content_fingerprint, "content_fingerprint")
        for value, name in (
            (self.grading_policy_id, "grading_policy_id"),
            (self.grading_policy_version, "grading_policy_version"),
            (self.grading_policy_fingerprint, "grading_policy_fingerprint"),
            (self.rubric_fingerprint, "rubric_fingerprint"),
        ):
            require_text(value, name)
        _fingerprint(self.grading_policy_fingerprint, "grading_policy_fingerprint")
        _fingerprint(self.rubric_fingerprint, "rubric_fingerprint")
        if self.assistance is not None:
            require_text(self.assistance, "assistance")
        if self.confidence_bps is not None and (
            type(self.confidence_bps) is not int or not 0 <= self.confidence_bps <= 10000
        ):
            raise ValueError("confidence_bps must be in 0..10000 or absent")
        if type(self.event_sequence) is not int or self.event_sequence <= 0:
            raise ValueError("learning evidence event sequence must be positive")


@dataclass(frozen=True, slots=True)
class LearningEvidenceSnapshot:
    course_id: CourseId
    through_sequence: int
    records: tuple[LearningEvidenceRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.course_id, CourseId):
            raise TypeError("learning evidence snapshot requires CourseId")
        if type(self.through_sequence) is not int or self.through_sequence < 0:
            raise ValueError("learning evidence snapshot sequence is invalid")
        values = tuple(self.records)
        if any(item.course_id != self.course_id for item in values):
            raise ValueError("learning evidence record course differs from snapshot")
        if tuple(item.event_sequence for item in values) != tuple(
            sorted(item.event_sequence for item in values)
        ):
            raise ValueError("learning evidence records are not in event order")
        if len({item.grade_id for item in values}) != len(values):
            raise ValueError("learning evidence records are duplicated")
        if any(item.event_sequence > self.through_sequence for item in values):
            raise ValueError("learning evidence record exceeds snapshot sequence")
        object.__setattr__(self, "records", values)


class ProjectionLearningEvidenceView:
    """Fail-closed read-only join of assessment facts and artifact provenance."""

    def __init__(self, assessments: AssessmentViewPort, artifacts: ArtifactViewPort) -> None:
        self._assessments = assessments
        self._artifacts = artifacts

    def get(self, course_id: CourseId) -> LearningEvidenceSnapshot:
        assessment = self._assessments.get(course_id)
        artifact = self._artifacts.get(course_id)
        if assessment.course_id != course_id or artifact.course_id != course_id:
            raise ValueError("learning evidence views returned another course")
        if assessment.sequence != artifact.sequence:
            raise ValueError("learning evidence views have divergent high-water marks")
        records: list[LearningEvidenceRecord] = []
        for grade in sorted(assessment.grades, key=lambda item: item.event_sequence):
            attempt = assessment.attempt(grade.attempt_id)
            presentation = assessment.presentation(attempt.presentation_id)
            _check_scope(grade, attempt, presentation, course_id)
            revision = artifact.revision(presentation.revision_id)
            _check_revision(revision, presentation.content_fingerprint)
            policy = _policy_fields(grade)
            records.append(
                LearningEvidenceRecord(
                    course_id,
                    grade.session_id,
                    revision.id,
                    presentation.id,
                    attempt.id,
                    grade.id,
                    tuple(revision.provenance.source_commitments),
                    presentation.content_fingerprint,
                    *policy,
                    grade.score,
                    grade.status,
                    grade.lifecycle,
                    tuple(grade.criterion_results),
                    None,
                    None,
                    grade.event_sequence,
                )
            )
        return LearningEvidenceSnapshot(course_id, assessment.sequence, tuple(records))


def _check_scope(
    grade: GradeRecord,
    attempt: AttemptRecord,
    presentation: PresentationRecord,
    course_id: CourseId,
) -> None:
    if (
        grade.course_id != course_id
        or attempt.course_id != course_id
        or presentation.course_id != course_id
    ):
        raise ValueError("learning evidence join contains a foreign course")
    if grade.session_id != attempt.session_id or attempt.session_id != presentation.session_id:
        raise ValueError("learning evidence join contains mismatched sessions")
    if grade.attempt_id != attempt.id or attempt.presentation_id != presentation.id:
        raise ValueError("learning evidence join identity is inconsistent")
    if grade.event_sequence <= 0:
        raise ValueError("learning evidence grade sequence is missing")


def _check_revision(revision: ArtifactRevisionRecord, content_fingerprint: str) -> None:
    from hashlib import sha256

    if revision.status is not ArtifactRevisionStatus.ACCEPTED:
        raise ValueError("learning evidence requires an accepted artifact revision")
    if sha256(revision.content.to_bytes()).hexdigest() != content_fingerprint:
        raise ValueError("learning evidence presentation content differs from artifact")
    if not revision.provenance.source_commitments:
        raise ValueError("learning evidence artifact has no source commitments")


def _policy_fields(grade: GradeRecord) -> tuple[str, str, str, str]:
    provenance = grade.provenance
    if isinstance(provenance, DeterministicGradeProvenance):
        return (
            provenance.policy_id,
            provenance.policy_version,
            provenance.policy_fingerprint,
            provenance.rubric_fingerprint,
        )
    return (
        provenance.capability_id,
        provenance.capability_version,
        provenance.capability_fingerprint,
        provenance.rubric_fingerprint,
    )


def _fingerprint(value: str, name: str) -> None:
    if type(value) is not str or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")


def learner_evidence_from(snapshot: AssessmentSnapshot) -> LearnerEvidenceSnapshot:
    contests = {item.grade_id: item for item in snapshot.contests}
    groups: dict[
        tuple[EvidenceDimension, str, str], list[LearnerEvidenceReference]
    ] = {}
    for grade in sorted(snapshot.grades, key=lambda item: item.event_sequence):
        attempt = snapshot.attempt(grade.attempt_id)
        presentation = snapshot.presentation(attempt.presentation_id)
        effective = grade.lifecycle is GradeLifecycle.ACTIVE and grade.id not in contests
        disposition = _grade_disposition(grade)
        format_group = (
            EvidenceDimension.FORMAT,
            presentation.content.format.value,
            presentation.content.format.value,
        )
        _add(
            groups,
            *format_group,
            LearnerEvidenceReference(
                grade.id,
                grade.event_sequence,
                disposition,
                grade.score.numerator if effective else 0,
                grade.score.denominator if effective else 0,
            ),
        )
        contest = contests.get(grade.id)
        if contest is not None:
            _add(
                groups,
                *format_group,
                LearnerEvidenceReference(
                    grade.id,
                    contest.event_sequence,
                    EvidenceDisposition.CONTESTED,
                    0,
                    0,
                ),
            )
        for ordinal, result in enumerate(grade.criterion_results):
            key = criterion_evidence_key(presentation.revision_id.value, ordinal, result.criterion)
            criterion_disposition = (
                disposition
                if not effective
                else EvidenceDisposition.SUPPORTING
                if result.status is CriterionStatus.MET
                else EvidenceDisposition.CONTRADICTING
                if result.status is CriterionStatus.NOT_MET
                else EvidenceDisposition.UNCERTAIN
            )
            _add(
                groups,
                EvidenceDimension.CRITERION,
                key,
                result.criterion,
                LearnerEvidenceReference(
                    grade.id,
                    grade.event_sequence,
                    criterion_disposition,
                    1 if effective and result.status is CriterionStatus.MET else 0,
                    1 if effective else 0,
                ),
            )
            if contest is not None:
                _add(
                    groups,
                    EvidenceDimension.CRITERION,
                    key,
                    result.criterion,
                    LearnerEvidenceReference(
                        grade.id,
                        contest.event_sequence,
                        EvidenceDisposition.CONTESTED,
                        0,
                        0,
                    ),
                )
    estimates = tuple(
        LearnerEvidenceEstimate(
            dimension,
            key,
            label,
            sum(item.numerator for item in references),
            sum(item.denominator for item in references),
            snapshot.sequence,
            tuple(references),
        )
        for (dimension, key, label), references in sorted(
            groups.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )
    return LearnerEvidenceSnapshot(snapshot.course_id, snapshot.sequence, estimates)


def criterion_evidence_key(revision_id: str, ordinal: int, criterion: str) -> str:
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("criterion ordinal must be non-negative")
    payload = canonical_json_bytes(
        {"revision_id": revision_id, "ordinal": ordinal, "criterion": criterion}
    )
    return f"criterion-sha256:{sha256(b'learner-evidence-criterion@1\0' + payload).hexdigest()}"


def _grade_disposition(grade: GradeRecord) -> EvidenceDisposition:
    if grade.lifecycle is GradeLifecycle.SUPERSEDED:
        return EvidenceDisposition.SUPERSEDED
    if grade.status is not GradeStatus.GRADED:
        return EvidenceDisposition.UNCERTAIN
    if grade.score.numerator == grade.score.denominator:
        return EvidenceDisposition.SUPPORTING
    if grade.score.numerator == 0:
        return EvidenceDisposition.CONTRADICTING
    return EvidenceDisposition.UNCERTAIN


def _add(
    groups: dict[tuple[EvidenceDimension, str, str], list[LearnerEvidenceReference]],
    dimension: EvidenceDimension,
    key: str,
    label: str,
    reference: LearnerEvidenceReference,
) -> None:
    groups.setdefault((dimension, key, label), []).append(reference)


__all__ = [
    "EvidenceDimension",
    "EvidenceDisposition",
    "LearnerEvidenceEstimate",
    "LearnerEvidenceReference",
    "LearnerEvidenceSnapshot",
    "LearningEvidenceRecord",
    "LearningEvidenceSnapshot",
    "ProjectionLearnerEvidenceView",
    "ProjectionLearningEvidenceView",
    "criterion_evidence_key",
    "learner_evidence_from",
]
