from __future__ import annotations

from study_agent.domain import ArtifactRevisionId, ExecutionContext
from study_agent.ports.recall import RecallCommandPort
from study_agent.recall.contracts import (
    RecallRating,
    RecallSnapshot,
    SchedulingPolicyConfigV1,
)


class _TypedRecallCommand:
    def enroll(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        policy: SchedulingPolicyConfigV1 | None = None,
    ) -> RecallSnapshot:
        raise NotImplementedError

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
    ) -> RecallSnapshot:
        raise NotImplementedError


def test_recall_command_port_matches_public_service_shape() -> None:
    port: RecallCommandPort = _TypedRecallCommand()
    assert port is not None
