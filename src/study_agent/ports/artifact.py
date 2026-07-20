"""Narrow ports for verified artifact writes and projection-only reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from study_agent.artifacts.contracts import (
        ArtifactSnapshot,
        ServiceDecisionPolicyReceipt,
        ServiceDecisionPolicyRequest,
        VerifiedGeneratedArtifactBatch,
    )
    from study_agent.domain import (
        CourseId,
        EventId,
        ExecutionContext,
        RunId,
        SourceCommitment,
    )


class VerifiedGeneratedBatchPort(Protocol):
    def recover(
        self, run_id: RunId, context: ExecutionContext
    ) -> VerifiedGeneratedArtifactBatch: ...


class SourceCommitmentLookupPort(Protocol):
    def contains(self, course_id: CourseId, commitment: SourceCommitment) -> bool: ...


class ServiceDecisionPolicyPort(Protocol):
    """Deterministic/idempotent policy keyed by ``request.request_id``."""

    def decide(self, request: ServiceDecisionPolicyRequest) -> ServiceDecisionPolicyReceipt: ...


class ArtifactViewPort(Protocol):
    def get(self, course_id: CourseId) -> ArtifactSnapshot: ...

    def command_fingerprint(self, course_id: CourseId, event_id: EventId) -> str | None: ...


__all__ = [
    "ArtifactViewPort",
    "ServiceDecisionPolicyPort",
    "SourceCommitmentLookupPort",
    "VerifiedGeneratedBatchPort",
]
