from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.adapters.scheduling.py_fsrs import (
    FSRS_ADAPTER_POLICY_ID,
    FSRS_ADAPTER_POLICY_VERSION,
    FSRS_CONFIGURATION_FINGERPRINT,
    FSRS_IMPLEMENTATION_ID,
    FSRS_IMPLEMENTATION_VERSION,
    FsrsAdapterError,
    FsrsUnavailableError,
    PyFsrsSchedulingPolicy,
)
from study_agent.domain import ArtifactRevisionId, ReviewId
from study_agent.recall.contracts import (
    RecallRating,
    ReviewHistoryEntry,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
)

NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
REVISION = ArtifactRevisionId("revision-1")


def _request(ratings: tuple[RecallRating, ...] = ()) -> SchedulingRequest:
    history = tuple(
        ReviewHistoryEntry(
            ReviewId(f"review-{index}"),
            REVISION,
            rating,
            None,
            None,
            NOW + timedelta(days=index),
        )
        for index, rating in enumerate(ratings, start=1)
    )
    return SchedulingRequest(REVISION, NOW, history, SchedulingPolicyConfigV1())


def _fsrs_available() -> bool:
    return importlib.util.find_spec("fsrs") is not None


@pytest.mark.skipif(not _fsrs_available(), reason="optional fsrs extra is not installed")
@pytest.mark.parametrize(
    ("ratings", "expected_due"),
    (
        ((), "2026-07-24T10:00:00+00:00"),
        ((RecallRating.AGAIN,), "2026-07-25T10:01:00+00:00"),
        ((RecallRating.HARD,), "2026-07-25T10:05:30+00:00"),
        ((RecallRating.GOOD,), "2026-07-25T10:10:00+00:00"),
        ((RecallRating.EASY,), "2026-08-02T10:00:00+00:00"),
        (
            (RecallRating.AGAIN, RecallRating.HARD, RecallRating.GOOD, RecallRating.EASY),
            "2026-08-04T10:00:00+00:00",
        ),
    ),
)
def test_golden_decisions_are_deterministic_and_provider_neutral(
    ratings: tuple[RecallRating, ...], expected_due: str
) -> None:
    request = _request(ratings)
    scheduler = PyFsrsSchedulingPolicy()
    result = scheduler.decide(request)
    repeated = scheduler.decide(request)

    assert result == repeated
    assert result.due_at.isoformat() == expected_due
    assert result.implementation_id == FSRS_IMPLEMENTATION_ID
    assert result.implementation_version == FSRS_IMPLEMENTATION_VERSION
    assert result.policy_id == FSRS_ADAPTER_POLICY_ID
    assert result.policy_version == FSRS_ADAPTER_POLICY_VERSION
    assert result.policy_fingerprint == scheduler.configuration_fingerprint_for(request.policy)
    assert result.history_fingerprint == request.history_fingerprint
    assert result.result_fingerprint != "0" * 64
    assert result.due_at.tzinfo is UTC
    assert result.due_at >= request.enrollment_at
    if request.history:
        assert result.due_at >= request.history[-1].occurred_at
    assert not hasattr(result, "card")
    assert not hasattr(result, "review_log")
    assert scheduler.configuration_fingerprint == FSRS_CONFIGURATION_FINGERPRINT
    assert scheduler.configuration_fingerprint_for(request.policy) != FSRS_CONFIGURATION_FINGERPRINT


def test_policy_options_are_passed_explicitly_and_affect_decision() -> None:
    if not _fsrs_available():
        pytest.skip("optional fsrs extra is not installed")
    baseline = _request((RecallRating.GOOD,))
    configured = replace(
        baseline,
        policy=SchedulingPolicyConfigV1(
            target_retention_bps=8500,
            maximum_interval_days=100,
            learning_steps_minutes=(2, 20),
            relearning_steps_minutes=(15,),
        ),
    )
    first = PyFsrsSchedulingPolicy().decide(baseline)
    second = PyFsrsSchedulingPolicy().decide(configured)
    assert first.due_at != second.due_at
    assert first.policy_fingerprint != second.policy_fingerprint
    assert PyFsrsSchedulingPolicy().configuration_fingerprint_for(
        baseline.policy
    ) != PyFsrsSchedulingPolicy().configuration_fingerprint_for(configured.policy)


def test_history_must_be_in_deterministic_order() -> None:
    if not _fsrs_available():
        pytest.skip("optional fsrs extra is not installed")
    later = ReviewHistoryEntry(
        ReviewId("review-1"), REVISION, RecallRating.GOOD, None, None, NOW + timedelta(days=2)
    )
    earlier = ReviewHistoryEntry(
        ReviewId("review-2"), REVISION, RecallRating.GOOD, None, None, NOW + timedelta(days=1)
    )
    with pytest.raises(FsrsAdapterError, match="deterministic time order"):
        PyFsrsSchedulingPolicy().decide(
            SchedulingRequest(REVISION, NOW, (later, earlier), SchedulingPolicyConfigV1())
        )


def test_missing_or_wrong_distribution_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "version", lambda _: "6.3.0")
    with pytest.raises(FsrsUnavailableError, match=r"exactly fsrs==6\.3\.1"):
        PyFsrsSchedulingPolicy()

    def missing(_: str) -> object:
        raise ModuleNotFoundError("fsrs")

    monkeypatch.setattr(importlib.metadata, "version", lambda _: "6.3.1")
    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(FsrsUnavailableError, match="cannot be imported"):
        PyFsrsSchedulingPolicy()


def test_base_adapter_import_does_not_require_optional_package() -> None:
    # Importing the adapter module is safe even when composition cannot create
    # an FSRS policy.  The optional package is loaded only at construction.
    import study_agent.adapters.scheduling.py_fsrs as adapter

    assert adapter.FSRS_IMPLEMENTATION_VERSION == "6.3.1"
