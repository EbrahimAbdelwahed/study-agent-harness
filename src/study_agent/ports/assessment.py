"""Read-only port for canonical assessment state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from study_agent.domain import CourseId

if TYPE_CHECKING:
    from study_agent.artifacts.content import AssessmentItemContent
    from study_agent.assessments.contracts import AssessmentSnapshot, CanonicalResponse
    from study_agent.assessments.grading import DeterministicGradeDecision


class AssessmentViewPort(Protocol):
    def get(self, course_id: CourseId) -> AssessmentSnapshot: ...


class DeterministicClosedGradingPolicyPort(Protocol):
    def grade(
        self, content: AssessmentItemContent, response: CanonicalResponse
    ) -> DeterministicGradeDecision: ...


__all__ = ["AssessmentViewPort", "DeterministicClosedGradingPolicyPort"]
