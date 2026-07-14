"""Projection-only public query contract for progressive study context."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import CourseId, EventId, StudyContextSnapshot


class StudyContextViewPort(Protocol):
    def get(self, course_id: CourseId) -> StudyContextSnapshot: ...

    def command_fingerprint(self, course_id: CourseId, event_id: EventId) -> str | None: ...
