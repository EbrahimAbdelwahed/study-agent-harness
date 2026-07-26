"""Read and write ports for optional recall composition."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain import ArtifactRevisionId, CourseId, ExecutionContext
from study_agent.recall.contracts import (
    RecallRating,
    RecallSnapshot,
    SchedulingPolicyConfigV1,
)


class RecallViewPort(Protocol):
    def get(self, course_id: CourseId) -> RecallSnapshot: ...


class RecallCommandPort(Protocol):
    def enroll(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        policy: SchedulingPolicyConfigV1 | None = None,
    ) -> RecallSnapshot: ...
    def review(
        self,
        revision_id: ArtifactRevisionId,
        rating: RecallRating,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        latency_ms: int | None = None,
        confidence_bps: int | None = None,
        policy: SchedulingPolicyConfigV1 | None = None,
    ) -> RecallSnapshot: ...


__all__ = ["RecallCommandPort", "RecallViewPort"]
