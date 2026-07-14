from __future__ import annotations

import pytest

from study_agent.lifecycle import (
    LifecycleActionKind,
    LifecycleActionOwner,
    LifecycleActionV1,
    LifecycleApplyReceiptV1,
    LifecycleApplyStatus,
    LifecycleCourseHighWater,
)


def test_apply_receipt_serialization_is_deterministic_and_fingerprinted() -> None:
    action = LifecycleActionV1(
        0,
        LifecycleActionKind.INITIALIZE,
        LifecycleActionOwner.REPOSITORY,
        "repository_absent",
        desired_fingerprint="a" * 64,
    )
    first = LifecycleApplyReceiptV1(
        LifecycleApplyStatus.APPLIED,
        "b" * 64,
        completed=(action,),
    )
    second = LifecycleApplyReceiptV1(
        LifecycleApplyStatus.APPLIED,
        "b" * 64,
        completed=(action,),
    )

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.fingerprint == second.fingerprint
    assert first.to_json()["fingerprint"] == first.fingerprint
    assert first.to_json()["completed"] == (action.to_json(),)


def _action(ordinal: int = 0) -> LifecycleActionV1:
    return LifecycleActionV1(
        ordinal,
        LifecycleActionKind.INITIALIZE,
        LifecycleActionOwner.REPOSITORY,
        "repository_absent",
        desired_fingerprint="a" * 64,
    )


def test_apply_receipt_rejects_overlapping_or_duplicate_categories() -> None:
    action = _action()

    with pytest.raises(ValueError, match="duplicates"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.APPLIED,
            "b" * 64,
            completed=(action, action),
        )
    with pytest.raises(ValueError, match="disjoint"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.CONFLICT,
            "b" * 64,
            completed=(action,),
            conflicts=(action,),
        )


def test_apply_receipt_requires_unique_ordered_authorized_plan_ordinals() -> None:
    first = _action(0)
    same_ordinal_different_action = LifecycleActionV1(
        0,
        LifecycleActionKind.REBUILD_INDEX,
        LifecycleActionOwner.INDEX,
        "index_missing",
    )
    later = _action(2)
    earlier = _action(1)

    with pytest.raises(ValueError, match="ordinals must be unique"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.CONFLICT,
            "b" * 64,
            completed=(first,),
            conflicts=(same_ordinal_different_action,),
        )
    with pytest.raises(ValueError, match="authorized plan order"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.CONFLICT,
            "b" * 64,
            remaining=(later, earlier),
        )


def test_apply_receipt_rejects_contradictory_status_categories() -> None:
    action = _action()

    with pytest.raises(ValueError, match="converged"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.CONVERGED,
            "b" * 64,
            completed=(action,),
        )
    with pytest.raises(ValueError, match="requires only completed"):
        LifecycleApplyReceiptV1(LifecycleApplyStatus.APPLIED, "b" * 64)
    with pytest.raises(ValueError, match="requires degraded"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.APPLIED_DEGRADED,
            "b" * 64,
            completed=(action,),
        )
    with pytest.raises(ValueError, match="outstanding canonical"):
        LifecycleApplyReceiptV1(LifecycleApplyStatus.CONFLICT, "b" * 64)


def test_apply_receipt_requires_unique_sorted_high_waters() -> None:
    action = _action()

    with pytest.raises(ValueError, match="unique by course"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.APPLIED,
            "b" * 64,
            completed=(action,),
            observed_high_waters=(
                LifecycleCourseHighWater("course-a", 1),
                LifecycleCourseHighWater("course-a", 2),
            ),
        )
    with pytest.raises(ValueError, match="sorted by course"):
        LifecycleApplyReceiptV1(
            LifecycleApplyStatus.APPLIED,
            "b" * 64,
            completed=(action,),
            observed_high_waters=(
                LifecycleCourseHighWater("course-b", 1),
                LifecycleCourseHighWater("course-a", 1),
            ),
        )
