"""Read and write ports for optional recall composition."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import ArtifactRevisionId, CourseId, SessionId
from study_agent.recall.contracts import RecallRating, RecallSnapshot


class RecallViewPort(Protocol):
    def get(self, course_id: CourseId) -> RecallSnapshot: ...


class RecallCommandPort(Protocol):
    def enroll(
        self,
        course_id: CourseId,
        session_id: SessionId,
        revision_id: ArtifactRevisionId,
        **kwargs: object,
    ) -> object: ...
    def review(
        self,
        course_id: CourseId,
        session_id: SessionId,
        revision_id: ArtifactRevisionId,
        rating: RecallRating,
        **kwargs: object,
    ) -> object: ...


__all__ = ["RecallCommandPort", "RecallViewPort"]
