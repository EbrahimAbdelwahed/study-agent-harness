"""Convergent lifecycle application over a narrow injected runtime boundary."""

from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from study_agent.domain.context import ExecutionContext
from study_agent.domain.identifiers import CourseId
from study_agent.ports.source_input import SourceSnapshot
from study_agent.repository_config import LocalRepositoryConfig

from .contracts import (
    DesiredCourse,
    DesiredSource,
    LifecycleActionKind,
    LifecycleActionV1,
    LifecycleApplyReceiptV1,
    LifecycleApplyStatus,
    LifecycleAuthority,
    LifecycleCourseHighWater,
    LifecycleManifestV1,
    LifecyclePlanV1,
    RepositoryObservation,
)
from .planner import desired_repository_config, plan_lifecycle

_ACTION_IDEMPOTENCY_DOMAIN = b"study-agent-lifecycle-action-v1\0"
_MUTABLE_KINDS = frozenset(
    {
        LifecycleActionKind.INITIALIZE,
        LifecycleActionKind.CREATE_COURSE,
        LifecycleActionKind.INGEST_REVISION,
        LifecycleActionKind.REBUILD_INDEX,
    }
)


class StaleLifecyclePlanError(RuntimeError):
    """The supplied plan is not the exact plan for fresh observed state."""

    def __init__(self, expected_plan: LifecyclePlanV1, observed_plan: LifecyclePlanV1) -> None:
        super().__init__(
            "lifecycle plan is stale: expected "
            f"{expected_plan.fingerprint}, observed {observed_plan.fingerprint}"
        )
        self.expected_plan = expected_plan
        self.observed_plan = observed_plan


class LifecycleRuntimeConflictError(RuntimeError):
    """A runtime mutation lost its expected-state compare-and-swap."""


class LifecycleRuntimeIndexError(RuntimeError):
    """The discardable retrieval rebuild failed operationally."""


class RetryableLifecycleConflictError(RuntimeError):
    """Apply stopped at a concurrency boundary and can be safely replanned."""

    def __init__(self, receipt: LifecycleApplyReceiptV1) -> None:
        super().__init__("lifecycle apply raced with canonical state; replan and retry")
        self.receipt = receipt


class LifecycleRuntime(Protocol):
    """Technical mutation boundary; implementations compose existing services."""

    def observe(self) -> RepositoryObservation: ...

    def initialize(self, config: LocalRepositoryConfig) -> None: ...

    def create_course(
        self,
        desired_course: DesiredCourse,
        context: ExecutionContext,
        expected_high_water: int,
    ) -> None: ...

    def ingest_source(
        self,
        desired_source: DesiredSource,
        snapshot: SourceSnapshot,
        context: ExecutionContext,
        expected_high_water: int,
    ) -> None: ...

    def rebuild_index(self) -> None: ...


class LifecycleService:
    """Apply a verified plan while revalidating every mutable ownership boundary."""

    def __init__(
        self, manifest: LifecycleManifestV1, runtime: LifecycleRuntime
    ) -> None:
        if not isinstance(manifest, LifecycleManifestV1):
            raise TypeError("manifest must be a LifecycleManifestV1")
        self._manifest = manifest
        self._runtime = runtime

    def apply(
        self,
        plan: LifecyclePlanV1,
        snapshots: tuple[SourceSnapshot, ...],
        authority: LifecycleAuthority,
    ) -> LifecycleApplyReceiptV1:
        if not isinstance(plan, LifecyclePlanV1):
            raise TypeError("plan must be a LifecyclePlanV1")
        if not isinstance(authority, LifecycleAuthority):
            raise TypeError("authority must be a LifecycleAuthority")

        initial_observation = self._runtime.observe()
        fresh_plan = plan_lifecycle(self._manifest, snapshots, initial_observation)
        if fresh_plan.canonical_bytes() != plan.canonical_bytes():
            raise StaleLifecyclePlanError(plan, fresh_plan)

        mutable_actions = tuple(
            action for action in plan.actions if action.kind in _MUTABLE_KINDS
        )
        passive_noops = tuple(
            action
            for action in plan.actions
            if action.kind in {LifecycleActionKind.NOOP, LifecycleActionKind.WARNING}
        )
        if plan.conflicts:
            return self._receipt(
                LifecycleApplyStatus.CONFLICT,
                plan,
                initial_observation,
                noops=passive_noops,
                remaining=mutable_actions,
                conflicts=plan.conflicts,
            )

        completed: list[LifecycleActionV1] = []
        noops = list(passive_noops)
        for action_index, action in enumerate(mutable_actions):
            observation = self._runtime.observe()
            current_plan = plan_lifecycle(self._manifest, snapshots, observation)
            current = _owned_action(current_plan, action)
            if current_plan.conflicts or not _still_applicable(action, current):
                receipt = self._receipt(
                    LifecycleApplyStatus.CONFLICT,
                    plan,
                    observation,
                    completed=tuple(completed),
                    noops=tuple(noops),
                    remaining=mutable_actions[action_index + 1 :],
                    conflicts=(action,),
                )
                raise RetryableLifecycleConflictError(receipt)
            if current is not None and current.kind is LifecycleActionKind.NOOP:
                noops.append(action)
                continue

            try:
                self._execute(plan.fingerprint, action, snapshots, authority)
            except LifecycleRuntimeConflictError as error:
                conflicted_observation = self._runtime.observe()
                receipt = self._receipt(
                    LifecycleApplyStatus.CONFLICT,
                    plan,
                    conflicted_observation,
                    completed=tuple(completed),
                    noops=tuple(noops),
                    remaining=mutable_actions[action_index + 1 :],
                    conflicts=(action,),
                )
                raise RetryableLifecycleConflictError(receipt) from error
            except LifecycleRuntimeIndexError:
                if action.kind is not LifecycleActionKind.REBUILD_INDEX:
                    raise
                degraded_observation = self._runtime.observe()
                return self._receipt(
                    LifecycleApplyStatus.APPLIED_DEGRADED,
                    plan,
                    degraded_observation,
                    completed=tuple(completed),
                    noops=tuple(noops),
                    degraded=(action,),
                    remaining=mutable_actions[action_index + 1 :],
                )
            completed.append(action)

        final_observation = self._runtime.observe()
        return self._receipt(
            LifecycleApplyStatus.APPLIED if completed else LifecycleApplyStatus.CONVERGED,
            plan,
            final_observation,
            completed=tuple(completed),
            noops=tuple(noops),
        )

    def _execute(
        self,
        plan_fingerprint: str,
        action: LifecycleActionV1,
        snapshots: tuple[SourceSnapshot, ...],
        authority: LifecycleAuthority,
    ) -> None:
        if action.kind is LifecycleActionKind.INITIALIZE:
            self._runtime.initialize(desired_repository_config(self._manifest))
            return
        if action.kind is LifecycleActionKind.REBUILD_INDEX:
            self._runtime.rebuild_index()
            return
        if action.course_id is None or action.expected_high_water is None:
            raise ValueError("canonical lifecycle action lacks course CAS coordinates")
        context = _execution_context(
            plan_fingerprint=plan_fingerprint, action=action, authority=authority
        )
        if action.kind is LifecycleActionKind.CREATE_COURSE:
            self._runtime.create_course(
                self._course(action.course_id), context, action.expected_high_water
            )
            return
        if action.kind is LifecycleActionKind.INGEST_REVISION:
            if action.source_id is None:
                raise ValueError("source lifecycle action lacks a source identity")
            source, snapshot = self._source_and_snapshot(
                action.course_id, action.source_id, snapshots
            )
            self._runtime.ingest_source(
                source, snapshot, context, action.expected_high_water
            )
            return
        raise ValueError("unsupported mutable lifecycle action")

    def _course(self, course_id: str) -> DesiredCourse:
        return next(course for course in self._manifest.courses if course.course_id == course_id)

    def _source_and_snapshot(
        self,
        course_id: str,
        source_id: str,
        snapshots: tuple[SourceSnapshot, ...],
    ) -> tuple[DesiredSource, SourceSnapshot]:
        index = 0
        for course in self._manifest.courses:
            for source in course.sources:
                if course.course_id == course_id and source.source_id == source_id:
                    return source, snapshots[index]
                index += 1
        raise ValueError("lifecycle source action is not owned by the manifest")

    @staticmethod
    def _receipt(
        status: LifecycleApplyStatus,
        plan: LifecyclePlanV1,
        observation: RepositoryObservation,
        *,
        completed: tuple[LifecycleActionV1, ...] = (),
        noops: tuple[LifecycleActionV1, ...] = (),
        degraded: tuple[LifecycleActionV1, ...] = (),
        remaining: tuple[LifecycleActionV1, ...] = (),
        conflicts: tuple[LifecycleActionV1, ...] = (),
    ) -> LifecycleApplyReceiptV1:
        high_waters = tuple(
            LifecycleCourseHighWater(course.course_id, course.high_water_sequence)
            for course in observation.courses
        )
        return LifecycleApplyReceiptV1(
            status,
            plan.fingerprint,
            completed,
            noops,
            degraded,
            remaining,
            conflicts,
            high_waters,
        )


def _owned_action(
    plan: LifecyclePlanV1, expected: LifecycleActionV1
) -> LifecycleActionV1 | None:
    return next(
        (
            action
            for action in plan.actions
            if action.owner is expected.owner
            and action.course_id == expected.course_id
            and action.source_id == expected.source_id
        ),
        None,
    )


def _still_applicable(
    expected: LifecycleActionV1, current: LifecycleActionV1 | None
) -> bool:
    if current is None:
        return False
    if current.kind is LifecycleActionKind.NOOP:
        return (
            current.desired_fingerprint == expected.desired_fingerprint
            or expected.kind is LifecycleActionKind.REBUILD_INDEX
        )
    if current.kind is not expected.kind:
        return False
    if expected.kind is LifecycleActionKind.REBUILD_INDEX:
        return True
    return (
        current.desired_fingerprint == expected.desired_fingerprint
        and current.expected_high_water == expected.expected_high_water
    )


def _execution_context(
    *,
    plan_fingerprint: str,
    action: LifecycleActionV1,
    authority: LifecycleAuthority,
) -> ExecutionContext:
    identity = f"{plan_fingerprint}\0{action.ordinal}".encode()
    digest = sha256(_ACTION_IDEMPOTENCY_DOMAIN + identity).hexdigest()
    return ExecutionContext(
        authority.principal_kind,
        authority.principal_id,
        CourseId(action.course_id or "repository"),
        authority.correlation_id,
        idempotency_key=f"lifecycle-action-sha256:{digest}",
    )


__all__ = [
    "LifecycleRuntime",
    "LifecycleRuntimeConflictError",
    "LifecycleRuntimeIndexError",
    "LifecycleService",
    "RetryableLifecycleConflictError",
    "StaleLifecyclePlanError",
]
