"""Read-only port for canonical assessment state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from study_agent.domain import CourseId

if TYPE_CHECKING:
    from study_agent.assessments.contracts import AssessmentSnapshot


class AssessmentViewPort(Protocol):
    def get(self, course_id: CourseId) -> AssessmentSnapshot: ...


__all__ = ["AssessmentViewPort"]
