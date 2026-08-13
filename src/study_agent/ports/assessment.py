"""Read-only port for canonical assessment state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    CourseId,
    ExecutionContext,
    GradeId,
    PresentationId,
    RunId,
)

if TYPE_CHECKING:
    from study_agent.artifacts.content import AssessmentItemContent
    from study_agent.assessments.contracts import (
        AssessmentSnapshot,
        AttemptRecord,
        CanonicalResponse,
        GradeContestRecord,
        GradeRecord,
        PresentationRecord,
    )
    from study_agent.assessments.evidence import LearnerEvidenceSnapshot
    from study_agent.assessments.grading import DeterministicGradeDecision
    from study_agent.assessments.verified_grading import VerifiedGradeOutcome


class AssessmentCommandPort(Protocol):
    """The typed host seam for assessment facts and observations."""

    def present_item(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> PresentationRecord: ...

    def record_attempt(
        self,
        presentation_id: PresentationId,
        response: CanonicalResponse,
        latency_ms: int | None,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> AttemptRecord: ...

    def grade_closed(
        self,
        attempt_id: AttemptId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        supersedes_grade_id: GradeId | None = None,
    ) -> GradeRecord: ...

    def record_verified_grade(
        self,
        run_id: RunId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        supersedes_grade_id: GradeId | None = None,
    ) -> GradeRecord: ...

    def contest_grade(
        self,
        grade_id: GradeId,
        reason: str,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> GradeContestRecord: ...


class AssessmentViewPort(Protocol):
    def get(self, course_id: CourseId) -> AssessmentSnapshot: ...


class DeterministicClosedGradingPolicyPort(Protocol):
    def grade(
        self, content: AssessmentItemContent, response: CanonicalResponse
    ) -> DeterministicGradeDecision: ...


class VerifiedGradeOwnerStore(Protocol):
    """Atomic owner slot for one completed grading child run."""

    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def load(self, run_id: RunId) -> bytes: ...


class VerifiedGradePort(Protocol):
    """Recover only a completed, proof-bound provider-neutral grade."""

    def recover(
        self, run_id: RunId, context: ExecutionContext
    ) -> VerifiedGradeOutcome: ...


class LearnerEvidenceViewPort(Protocol):
    def get(self, course_id: CourseId) -> LearnerEvidenceSnapshot: ...


__all__ = [
    "AssessmentCommandPort",
    "AssessmentViewPort",
    "DeterministicClosedGradingPolicyPort",
    "LearnerEvidenceViewPort",
    "VerifiedGradeOwnerStore",
    "VerifiedGradePort",
]
