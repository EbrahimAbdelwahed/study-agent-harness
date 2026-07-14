from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

import pytest

from study_agent.domain import CorrelationId, ExecutionContext, PrincipalKind
from study_agent.lifecycle import (
    DesiredCourse,
    DesiredRepository,
    DesiredSource,
    IndexObservationState,
    LifecycleApplyStatus,
    LifecycleAuthority,
    LifecycleManifestV1,
    LifecycleRuntimeConflictError,
    LifecycleRuntimeIndexError,
    LifecycleService,
    ObservedCourse,
    ObservedIndex,
    ObservedSource,
    RepositoryObservation,
    RepositoryObservationState,
    RetryableLifecycleConflictError,
    StaleLifecyclePlanError,
    desired_course_profile,
    desired_source_kind,
    desired_source_title,
    plan_lifecycle,
)
from study_agent.ports.source_input import SourceSnapshot
from study_agent.repository_config import LocalRepositoryConfig


def _manifest() -> LifecycleManifestV1:
    return LifecycleManifestV1(
        DesiredRepository("repository", None),
        (
            DesiredCourse(
                "course-a",
                "Anatomy",
                "en",
                None,
                ("Understand anatomy",),
                (),
                (DesiredSource("source-a", "notes.md", None, 90, "lecture"),),
            ),
        ),
    )


def _snapshot() -> SourceSnapshot:
    content = b"# Notes\n"
    return SourceSnapshot("notes.md", content, sha256(content).hexdigest(), len(content))


@dataclass
class FakeRuntime:
    state: RepositoryObservationState = RepositoryObservationState.COMPATIBLE
    course: ObservedCourse | None = None
    index_state: IndexObservationState = IndexObservationState.MISSING
    fail_kind: str | None = None
    calls: list[str] = field(default_factory=list)
    contexts: list[ExecutionContext] = field(default_factory=list)

    def observe(self) -> RepositoryObservation:
        if self.state is RepositoryObservationState.ABSENT:
            return RepositoryObservation(self.state)
        return RepositoryObservation(
            self.state,
            LocalRepositoryConfig(None),
            () if self.course is None else (self.course,),
            ObservedIndex(self.index_state),
        )

    def initialize(self, config: LocalRepositoryConfig) -> None:
        assert config == LocalRepositoryConfig(None)
        self.calls.append("initialize")
        self.state = RepositoryObservationState.COMPATIBLE

    def create_course(
        self,
        desired_course: DesiredCourse,
        context: ExecutionContext,
        expected_high_water: int,
    ) -> None:
        self._maybe_fail("create_course")
        assert expected_high_water == 0
        self.calls.append("create_course")
        self.contexts.append(context)
        self.course = ObservedCourse(desired_course_profile(desired_course), 1)

    def ingest_source(
        self,
        desired_source: DesiredSource,
        snapshot: SourceSnapshot,
        context: ExecutionContext,
        expected_high_water: int,
    ) -> None:
        self._maybe_fail("ingest_source")
        assert self.course is not None
        assert expected_high_water == self.course.high_water_sequence
        self.calls.append("ingest_source")
        self.contexts.append(context)
        observed_source = ObservedSource(
            desired_source.source_id,
            "revision-sha256:" + "a" * 64,
            desired_source_kind(desired_source),
            desired_source_title(desired_source),
            desired_source.trust_level,
            desired_source.source_role,
            snapshot.checksum_sha256,
            snapshot.byte_size,
        )
        self.course = ObservedCourse(
            self.course.profile,
            self.course.high_water_sequence + 1,
            (observed_source,),
        )

    def rebuild_index(self) -> None:
        if self.fail_kind == "rebuild_index":
            raise LifecycleRuntimeIndexError("retrieval unavailable")
        self.calls.append("rebuild_index")
        self.index_state = IndexObservationState.HEALTHY

    def _maybe_fail(self, kind: str) -> None:
        if self.fail_kind == kind:
            raise LifecycleRuntimeConflictError("CAS lost")


def _authority() -> LifecycleAuthority:
    return LifecycleAuthority(
        PrincipalKind.SERVICE,
        "study-agent-cli",
        CorrelationId("trusted-host-correlation"),
    )


def test_apply_converges_and_a_second_fresh_apply_has_no_mutations() -> None:
    manifest = _manifest()
    snapshots = (_snapshot(),)
    runtime = FakeRuntime()
    initial = plan_lifecycle(manifest, snapshots, runtime.observe())

    receipt = LifecycleService(manifest, runtime).apply(initial, snapshots, _authority())

    assert receipt.status is LifecycleApplyStatus.APPLIED
    assert runtime.calls == ["create_course", "ingest_source", "rebuild_index"]
    assert tuple(item.sequence for item in receipt.observed_high_waters) == (2,)
    assert all(context.principal_id == "study-agent-cli" for context in runtime.contexts)
    assert all(
        str(context.correlation_id) == "trusted-host-correlation"
        for context in runtime.contexts
    )
    assert len({context.idempotency_key for context in runtime.contexts}) == 2

    converged = plan_lifecycle(manifest, snapshots, runtime.observe())
    second = LifecycleService(manifest, runtime).apply(converged, snapshots, _authority())

    assert second.status is LifecycleApplyStatus.CONVERGED
    assert runtime.calls == ["create_course", "ingest_source", "rebuild_index"]


def test_stale_plan_is_rejected_before_mutation() -> None:
    manifest = _manifest()
    snapshot = _snapshot()
    runtime = FakeRuntime()
    plan = plan_lifecycle(manifest, (snapshot,), runtime.observe())
    runtime.create_course(manifest.courses[0], ExecutionContext(
        PrincipalKind.SERVICE,
        "other",
        desired_course_profile(manifest.courses[0]).id,
        runtime_context_correlation(),
    ), 0)
    runtime.calls.clear()

    with pytest.raises(StaleLifecyclePlanError):
        LifecycleService(manifest, runtime).apply(plan, (snapshot,), _authority())

    assert runtime.calls == []


def runtime_context_correlation() -> CorrelationId:
    return CorrelationId("concurrent-test")


def test_runtime_cas_conflict_reports_completed_and_remaining_work() -> None:
    manifest = _manifest()
    snapshots = (_snapshot(),)
    runtime = FakeRuntime(fail_kind="ingest_source")
    plan = plan_lifecycle(manifest, snapshots, runtime.observe())

    with pytest.raises(RetryableLifecycleConflictError) as raised:
        LifecycleService(manifest, runtime).apply(plan, snapshots, _authority())

    receipt = raised.value.receipt
    assert receipt.status is LifecycleApplyStatus.CONFLICT
    assert tuple(action.kind.value for action in receipt.completed) == ("create_course",)
    assert tuple(action.kind.value for action in receipt.remaining) == (
        "rebuild_index",
    )
    assert tuple(action.kind.value for action in receipt.conflicts) == ("ingest_revision",)
    assert runtime.calls == ["create_course"]


def test_revalidation_conflict_reports_only_the_authorized_plan_action() -> None:
    manifest = _manifest()
    snapshots = (_snapshot(),)
    runtime = FakeRuntime()
    plan = plan_lifecycle(manifest, snapshots, runtime.observe())
    original_observe = runtime.observe
    observation_count = 0

    def conflict_after_authorization() -> RepositoryObservation:
        nonlocal observation_count
        observation_count += 1
        if observation_count >= 2:
            return RepositoryObservation(
                RepositoryObservationState.CONFLICT,
                LocalRepositoryConfig(None),
            )
        return original_observe()

    runtime.observe = conflict_after_authorization  # type: ignore[method-assign]

    with pytest.raises(RetryableLifecycleConflictError) as raised:
        LifecycleService(manifest, runtime).apply(plan, snapshots, _authority())

    receipt = raised.value.receipt
    assert receipt.plan_fingerprint == plan.fingerprint
    assert receipt.conflicts == (plan.actions[1],)
    assert receipt.remaining == plan.actions[2:]
    assert set(action.ordinal for action in receipt.conflicts).isdisjoint(
        action.ordinal for action in receipt.remaining
    )


def test_index_failure_preserves_canonical_work_as_degraded() -> None:
    manifest = _manifest()
    snapshots = (_snapshot(),)
    runtime = FakeRuntime(fail_kind="rebuild_index")
    plan = plan_lifecycle(manifest, snapshots, runtime.observe())

    receipt = LifecycleService(manifest, runtime).apply(plan, snapshots, _authority())

    assert receipt.status is LifecycleApplyStatus.APPLIED_DEGRADED
    assert tuple(action.kind.value for action in receipt.completed) == (
        "create_course",
        "ingest_revision",
    )
    assert tuple(action.kind.value for action in receipt.degraded) == ("rebuild_index",)


def test_absent_repository_apply_is_initialization_only() -> None:
    manifest = _manifest()
    snapshots = (_snapshot(),)
    runtime = FakeRuntime(state=RepositoryObservationState.ABSENT)
    plan = plan_lifecycle(manifest, snapshots, runtime.observe())

    receipt = LifecycleService(manifest, runtime).apply(plan, snapshots, _authority())

    assert receipt.status is LifecycleApplyStatus.APPLIED
    assert runtime.calls == ["initialize"]
    next_plan = plan_lifecycle(manifest, snapshots, runtime.observe())
    assert any(action.kind.value == "create_course" for action in next_plan.actions)


def test_model_cannot_be_lifecycle_authority() -> None:
    with pytest.raises(ValueError, match="human or service"):
        LifecycleAuthority(
            PrincipalKind.MODEL,
            "model",
            CorrelationId("trusted-host-correlation"),
        )


def test_lifecycle_authority_requires_host_supplied_correlation() -> None:
    with pytest.raises(ValueError, match="correlation_id"):
        LifecycleAuthority(
            PrincipalKind.SERVICE,
            "study-agent-cli",
            "manifest-correlation",  # type: ignore[arg-type]
        )
