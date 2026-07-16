"""Pure learner-evidence projection over canonical assessment history."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from study_agent.domain import (
    CourseId,
    CriterionStatus,
    GradeId,
    GradeLifecycle,
    GradeStatus,
)
from study_agent.ports.assessment import AssessmentViewPort
from study_agent.state import canonical_json_bytes

from .contracts import AssessmentSnapshot, GradeRecord


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
    "ProjectionLearnerEvidenceView",
    "criterion_evidence_key",
    "learner_evidence_from",
]
