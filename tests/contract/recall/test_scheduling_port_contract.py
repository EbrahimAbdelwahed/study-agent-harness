from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import ArtifactRevisionId, ReviewId
from study_agent.ports.scheduling import SchedulingPolicyPort
from study_agent.recall.contracts import (
    RecallRating,
    ReviewHistoryEntry,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)

NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)


class FakeScheduler:
    def decide(self, request: SchedulingRequest) -> SchedulingResult:
        partial = SchedulingResult(
            NOW + timedelta(days=1),
            "fake",
            "1",
            effective_policy_fingerprint(request.policy, "fake", "1", "fake", "1"),
            "fake",
            "1",
            request.history_fingerprint,
            "0" * 64,
        )
        return replace(partial, result_fingerprint=result_fingerprint(request, partial))


def test_structural_scheduler_uses_only_provider_neutral_dtos() -> None:
    request = SchedulingRequest(
        ArtifactRevisionId("revision-1"),
        NOW,
        (
            ReviewHistoryEntry(
                ReviewId("review-1"),
                ArtifactRevisionId("revision-1"),
                RecallRating.GOOD,
                100,
                8000,
                NOW + timedelta(minutes=1),
            ),
        ),
        SchedulingPolicyConfigV1(),
    )
    scheduler: SchedulingPolicyPort = FakeScheduler()
    result = scheduler.decide(request)
    assert result.history_fingerprint == request.history_fingerprint
    assert result.result_fingerprint == result_fingerprint(request, result)
    assert not hasattr(result, "card")
    assert not hasattr(result, "review_log")


def test_scheduler_request_rejects_opaque_package_state_and_floats() -> None:
    with pytest.raises((TypeError, ValueError)):
        SchedulingPolicyConfigV1.from_json(
            {
                **SchedulingPolicyConfigV1().to_json(),
                "serialized_state": "card",
            }
        )
    with pytest.raises(ValueError):
        ReviewHistoryEntry(
            ReviewId("review-1"),
            ArtifactRevisionId("revision-1"),
            RecallRating.GOOD,
            1.5,  # type: ignore[arg-type]
            None,
            NOW,
        )


def test_effective_policy_fingerprint_binds_core_and_adapter_identities() -> None:
    policy = SchedulingPolicyConfigV1()
    baseline = effective_policy_fingerprint(policy, "fake", "1", "fake", "1")
    assert baseline != effective_policy_fingerprint(policy, "fake", "2", "fake", "1")
    assert baseline != effective_policy_fingerprint(policy, "fake", "1", "fake", "2")
    assert baseline != effective_policy_fingerprint(
        SchedulingPolicyConfigV1(8500), "fake", "1", "fake", "1"
    )
