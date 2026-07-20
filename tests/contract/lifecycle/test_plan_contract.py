from __future__ import annotations

from hashlib import sha256

import pytest

from study_agent.lifecycle import (
    LifecycleActionKind,
    LifecycleActionOwner,
    LifecycleActionV1,
    LifecyclePlanV1,
    LifecycleSourceChecksum,
)

SHA = "a" * 64


def test_plan_fingerprint_is_canonical_and_includes_derived_views() -> None:
    action = LifecycleActionV1(
        0,
        LifecycleActionKind.WARNING,
        LifecycleActionOwner.SOURCE,
        "source_removed_from_manifest_ignored",
        "course-a",
        "source-a",
        2,
    )
    plan = LifecyclePlanV1(
        SHA,
        (LifecycleSourceChecksum("course-a", "source-a", "a.md", SHA, 1),),
        (),
        (action,),
    )

    assert plan.canonical_bytes() == plan.canonical_bytes()
    assert len(plan.fingerprint) == 64
    assert plan.to_json()["warnings"] == (action.to_json(),)
    assert plan.to_json()["conflicts"] == ()
    assert sha256(plan.canonical_bytes()).hexdigest() != plan.fingerprint


def test_plan_rejects_non_contiguous_action_ordinals() -> None:
    action = LifecycleActionV1(
        1,
        LifecycleActionKind.NOOP,
        LifecycleActionOwner.REPOSITORY,
        "repository_compatible",
    )

    with pytest.raises(ValueError, match="contiguous"):
        LifecyclePlanV1(SHA, (), (), (action,))
