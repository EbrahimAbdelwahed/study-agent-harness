"""Host-facing read contract for sequence-consistent tutor snapshots."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import CourseId, SessionId, TutorSnapshotV1


class TutorSnapshotPort(Protocol):
    def get(self, course_id: CourseId, session_id: SessionId) -> TutorSnapshotV1: ...


__all__ = ["TutorSnapshotPort"]
