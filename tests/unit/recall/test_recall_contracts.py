from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import ArtifactRevisionId, CourseId, ReviewId, ScheduleDecisionId
from study_agent.recall.contracts import (
    AppliedSchedule,
    RecallRating,
    ReviewHistoryEntry,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    history_fingerprint,
    result_fingerprint,
)

NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
REVISION = ArtifactRevisionId("revision-1")
REVIEW = ReviewId("review-1")
COURSE = CourseId("course-1")


def _entry(
    *,
    review_id: ReviewId = REVIEW,
    rating: RecallRating = RecallRating.GOOD,
    occurred_at: datetime = NOW + timedelta(minutes=1),
    latency_ms: int | None = 1200,
    confidence_bps: int | None = 8500,
) -> ReviewHistoryEntry:
    return ReviewHistoryEntry(review_id, REVISION, rating, latency_ms, confidence_bps, occurred_at)


def _request(
    *,
    policy: SchedulingPolicyConfigV1 | None = None,
    history: tuple[ReviewHistoryEntry, ...] = (),
) -> SchedulingRequest:
    return SchedulingRequest(REVISION, NOW, history, policy or SchedulingPolicyConfigV1())


def _result(
    request: SchedulingRequest, *, due_at: datetime = NOW + timedelta(days=1)
) -> SchedulingResult:
    partial = SchedulingResult(
        due_at,
        "deterministic",
        "1",
        effective_policy_fingerprint(request.policy, "deterministic", "1", "fake", "1"),
        "fake",
        "1",
        request.history_fingerprint,
        "0" * 64,
    )
    return replace(partial, result_fingerprint=result_fingerprint(request, partial))


def test_policy_codec_and_fingerprint_are_canonical() -> None:
    policy = SchedulingPolicyConfigV1(8700, 1000, (1, 5, 20), (10,))
    assert SchedulingPolicyConfigV1.from_json(policy.to_json()) == policy
    assert policy.fingerprint == SchedulingPolicyConfigV1.from_json(policy.to_json()).fingerprint
    with pytest.raises(ValueError):
        SchedulingPolicyConfigV1.from_json({**policy.to_json(), "provider": "fsrs"})
    with pytest.raises(ValueError):
        SchedulingPolicyConfigV1.from_json({**policy.to_json(), "target_retention_bps": 0.9})


def test_history_and_result_fingerprints_bind_every_effective_input() -> None:
    first = _entry()
    request = _request(history=(first,))
    baseline = history_fingerprint(REVISION, NOW, (first,))
    assert baseline == request.history_fingerprint
    assert (
        history_fingerprint(REVISION, NOW, (replace(first, rating=RecallRating.EASY),)) != baseline
    )
    assert history_fingerprint(REVISION, NOW, (replace(first, latency_ms=1201),)) != baseline
    assert history_fingerprint(REVISION, NOW, (replace(first, confidence_bps=8501),)) != baseline
    assert (
        history_fingerprint(
            REVISION, NOW, (replace(first, occurred_at=NOW + timedelta(minutes=2)),)
        )
        != baseline
    )
    assert (
        history_fingerprint(
            REVISION,
            NOW,
            (
                first,
                ReviewHistoryEntry(
                    ReviewId("review-2"),
                    REVISION,
                    RecallRating.HARD,
                    None,
                    None,
                    NOW + timedelta(minutes=2),
                ),
            ),
        )
        != baseline
    )

    result = _result(request)
    assert result_fingerprint(request, result) == result.result_fingerprint
    assert (
        result_fingerprint(request, replace(result, due_at=result.due_at + timedelta(seconds=1)))
        != result.result_fingerprint
    )
    changed_policy = replace(request, policy=SchedulingPolicyConfigV1(8800))
    assert result_fingerprint(changed_policy, _result(changed_policy)) != result.result_fingerprint
    changed_implementation = replace(
        result,
        implementation_version="2",
        policy_fingerprint=effective_policy_fingerprint(
            request.policy, "deterministic", "1", "fake", "2"
        ),
    )
    assert (
        result_fingerprint(request, changed_implementation)
        != result.result_fingerprint
    )


def test_request_rejects_duplicate_or_cross_revision_history() -> None:
    first = _entry()
    with pytest.raises(ValueError):
        _request(history=(first, first))
    with pytest.raises(ValueError):
        SchedulingRequest(
            REVISION,
            NOW,
            (
                ReviewHistoryEntry(
                    REVIEW, ArtifactRevisionId("other"), RecallRating.GOOD, None, None, NOW
                ),
            ),
            SchedulingPolicyConfigV1(),
        )


def test_schedule_receipt_rejects_forged_policy_fingerprint() -> None:
    request = _request()
    result = _result(request)
    with pytest.raises(ValueError):
        AppliedSchedule(
            ScheduleDecisionId("decision-1"),
            REVISION,
            "enrollment",
            None,
            NOW,
            result.due_at,
            request.policy,
            result.policy_id,
            result.policy_version,
            "f" * 64,
            result.implementation_id,
            result.implementation_version,
            result.history_fingerprint,
            result.result_fingerprint,
            "enroll-key",
            "e" * 64,
        )


def test_schedule_receipt_is_immutable_and_normalizes_utc() -> None:
    request = _request()
    result = _result(request)
    schedule = AppliedSchedule(
        ScheduleDecisionId("decision-1"),
        REVISION,
        "enrollment",
        None,
        NOW,
        result.due_at,
        request.policy,
        result.policy_id,
        result.policy_version,
        result.policy_fingerprint,
        result.implementation_id,
        result.implementation_version,
        result.history_fingerprint,
        result.result_fingerprint,
        "enroll-key",
        "e" * 64,
    )
    assert schedule.enrollment_at.tzinfo is UTC
    with pytest.raises((AttributeError, TypeError)):
        schedule.due_at = NOW  # type: ignore[misc]
