from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from typing import NoReturn

import pytest

from study_agent.capabilities import TutorCapabilityId
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RevisionId,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject
from study_agent.flashcards.lesson_worker_contracts import (
    LessonWorkerCheckpoint,
    LessonWorkerPageStatus,
    LessonWorkerRequest,
    ResolvedPlannedBundleEvidence,
    RevisionContentCommitment,
    VerifiedFlashcardPageResult,
)
from study_agent.flashcards.lesson_worker_service import (
    LessonWorkerConflictError,
    LessonWorkerService,
)
from study_agent.flashcards.planning import PreparedPlannedFlashcardScope
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.state import canonical_json_bytes
from study_agent.workers import (
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    GenerationWorkerTaskKind,
    fingerprint_output_schema,
)
from study_agent.workers.view import WorkerCompactView, WorkerDetailView
from tests.unit.flashcards.test_lesson_worker_contracts import (
    _multi_plan,
    _no_work_plan,
    _request,
    _wrapper,
)


def _parent(principal: str = "tutor-service") -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.SERVICE,
        principal,
        CourseId("course-1"),
        CorrelationId("correlation-1"),
        frozenset({"source.read"}),
        SessionId("session-1"),
        idempotency_key="lesson-retry",
    )


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def create(self, key: str, payload: bytes) -> bool:
        if key in self.values:
            return False
        self.values[key] = payload
        return True

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool:
        if self.values[key] != expected:
            return False
        self.values[key] = replacement
        return True

    def load(self, key: str) -> bytes:
        return self.values[key]


class _CrashAfterStatusStore(_Store):
    def __init__(self, status: LessonWorkerPageStatus) -> None:
        super().__init__()
        self.status = status
        self.crashed = False

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool:
        changed = super().compare_and_set(key, expected, replacement)
        checkpoint = LessonWorkerCheckpoint.from_bytes(replacement)
        if (
            changed
            and not self.crashed
            and checkpoint.pages[0].status is self.status
        ):
            self.crashed = True
            raise RuntimeError(f"crash after {self.status.value}")
        return changed


class _CrashBeforeStatusStore(_Store):
    def __init__(self, status: LessonWorkerPageStatus) -> None:
        super().__init__()
        self.status = status
        self.crashed = False

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool:
        checkpoint = LessonWorkerCheckpoint.from_bytes(replacement)
        if not self.crashed and checkpoint.pages[0].status is self.status:
            self.crashed = True
            raise RuntimeError(f"crash before {self.status.value}")
        return super().compare_and_set(key, expected, replacement)


class _WinningRaceStore(_Store):
    def __init__(self) -> None:
        super().__init__()
        self.raced = False

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool:
        if not self.raced:
            self.raced = True
            assert self.values[key] == expected
            self.values[key] = replacement
            return False
        return super().compare_and_set(key, expected, replacement)


class _ConflictingRaceStore(_Store):
    def __init__(self) -> None:
        super().__init__()
        self.raced = False

    def compare_and_set(self, key: str, expected: bytes, replacement: bytes) -> bool:
        if not self.raced:
            self.raced = True
            checkpoint = LessonWorkerCheckpoint.from_bytes(expected)
            self.values[key] = replace(
                checkpoint,
                authority_fingerprint="f" * 64,
            ).to_bytes()
            return False
        return super().compare_and_set(key, expected, replacement)


class _Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, plan, bundle, revision_commitments, context):  # type: ignore[no-untyped-def]
        self.calls += 1
        request = _request(plan=plan, revision_commitments=revision_commitments)
        return ResolvedPlannedBundleEvidence(
            _wrapper(request, bundle.relative_position).prepared_scope.evidence,
            revision_commitments,
            plan.plan_fingerprint,
            bundle.bundle_id,
        )


class _Binding:
    def __init__(self, request) -> None:  # type: ignore[no-untyped-def]
        self.expectation = request.profile_expectation
        self.request = request
        self.calls = 0

    def build(self, task_id, public_inputs, prepared_scope, context):  # type: ignore[no-untyped-def]
        self.calls += 1
        bundle = next(
            item
            for item in self.request.plan.bundles
            if item.bundle_id == prepared_scope.bundle_id
        )
        bundle_fingerprint = sha256(
            b"lesson-worker-bundle@1\0" + canonical_json_bytes(bundle.to_json())
        ).hexdigest()
        expectation = self.expectation
        return GenerationWorkerTask(
            task_id=task_id,
            task_kind=GenerationWorkerTaskKind.FLASHCARD_BUNDLE,
            capability_id=expectation.capability_id,
            capability_version=expectation.capability_version,
            manifest_fingerprint=expectation.manifest_fingerprint,
            required_authority=expectation.required_authority,
            pins=expectation.pins,
            definition_fingerprint=expectation.definition_fingerprint,
            language=self.request.language,
            preferences={},
            continuation_summary=self.request.continuation_summary,
            index_references=(
                f"plan-sha256:{self.request.plan.plan_fingerprint}",
                f"bundle-sha256:{bundle_fingerprint}",
                f"wrapper-sha256:{prepared_scope.wrapper_fingerprint}",
                f"read-set-sha256:{prepared_scope.prepared_scope.evidence.read_set_fingerprint}",
                f"revisions-sha256:{self.request.revision_commitments_fingerprint}",
                f"profile-sha256:{expectation.fingerprint}",
            ),
            evidence_references=tuple(
                item.handle for item in prepared_scope.prepared_scope.evidence.items
            ),
            payload=public_inputs,
            output_schema=expectation.output_schema,
            output_schema_fingerprint=expectation.output_schema_fingerprint,
            expected_validations=expectation.validations,
        )


class _RunningWorker:
    def __init__(self) -> None:
        self.starts: list[tuple[GenerationWorkerTask, PreparedPlannedFlashcardScope]] = []

    async def start(self, task, prepared_scope, context):  # type: ignore[no-untyped-def]
        self.starts.append((task, prepared_scope))
        return WorkerCompactView(
            task.task_id,
            task.task_kind,
            GenerationWorkerStatus.RUNNING,
            0,
            task.fingerprint,
            RunId("child-run"),
            None,
            None,
            False,
        )

    def detail(self, task_id, prepared_scope_fingerprint, context) -> NoReturn:  # type: ignore[no-untyped-def]
        raise AssertionError("running children have no verified detail")


def _completed_result(task: GenerationWorkerTask, count: int) -> VerifiedFlashcardPageResult:
    output_fingerprint = "d" * 64
    receipt = GenerationWorkerReceipt(
        task_id=task.task_id,
        task_kind=task.task_kind,
        status=GenerationWorkerStatus.COMPLETED,
        child_run_id=RunId(f"run-{task.task_id[-12:]}"),
        task_fingerprint=task.fingerprint,
        pins_fingerprint=task.pins_fingerprint,
        input_fingerprint=task.payload_fingerprint,
        output_fingerprint=output_fingerprint,
        validator_fingerprint="b" * 64,
        run_fingerprint="c" * 64,
        prompt_fingerprint="a" * 64,
    )
    return VerifiedFlashcardPageResult(
        count,
        1,
        output_fingerprint,
        WorkerDetailView(receipt, {"private": f"candidate-body-{count}"}),
    )


class _ScriptedWorker:
    def __init__(
        self,
        scripts: dict[int, list[GenerationWorkerStatus]],
        counts: dict[int, int] | None = None,
    ) -> None:
        self.scripts = {position: list(statuses) for position, statuses in scripts.items()}
        self.counts = counts or {}
        self.tasks: dict[str, GenerationWorkerTask] = {}
        self.positions: dict[str, int] = {}
        self.results: dict[str, VerifiedFlashcardPageResult] = {}
        self.starts: list[str] = []

    async def start(self, task, prepared_scope, context):  # type: ignore[no-untyped-def]
        self.starts.append(task.task_id)
        position = self.positions.get(task.task_id, len(set(self.positions.values())))
        self.tasks[task.task_id] = task
        self.positions[task.task_id] = position
        statuses = self.scripts[position]
        status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
        result = (
            _completed_result(task, self.counts.get(position, position + 1))
            if status is GenerationWorkerStatus.COMPLETED
            else None
        )
        if result is not None:
            self.results[task.task_id] = result
        terminal = status.is_terminal
        return WorkerCompactView(
            task.task_id,
            task.task_kind,
            status,
            0,
            task.fingerprint,
            (
                RunId(f"run-{task.task_id[-12:]}")
                if status is not GenerationWorkerStatus.PENDING
                else None
            ),
            (
                result.detail.receipt.fingerprint
                if result is not None
                else "e" * 64
                if terminal
                else None
            ),
            status.value if terminal and status is not GenerationWorkerStatus.COMPLETED else None,
            status is GenerationWorkerStatus.COMPLETED,
        )

    def detail(self, task_id, prepared_scope_fingerprint, context):  # type: ignore[no-untyped-def]
        return self.results[task_id]


class _MutatingDetailWorker(_ScriptedWorker):
    def __init__(
        self,
        mutation: Callable[[GenerationWorkerReceipt], GenerationWorkerReceipt],
    ) -> None:
        super().__init__({0: [GenerationWorkerStatus.COMPLETED]})
        self.mutation = mutation

    def detail(self, task_id, prepared_scope_fingerprint, context):  # type: ignore[no-untyped-def]
        original = self.results[task_id]
        changed_receipt = self.mutation(original.detail.receipt)
        return replace(
            original,
            detail=WorkerDetailView(changed_receipt, original.detail.output),
        )


class _MutatingBinding(_Binding):
    def __init__(
        self,
        request: LessonWorkerRequest,
        mutation: Callable[[GenerationWorkerTask], GenerationWorkerTask],
    ) -> None:
        super().__init__(request)
        self.mutation = mutation

    def build(self, task_id, public_inputs, prepared_scope, context):  # type: ignore[no-untyped-def]
        task = super().build(  # type: ignore[no-untyped-call]
            task_id, public_inputs, prepared_scope, context
        )
        return self.mutation(task)


_CHANGED_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {},
    "required": (),
    "additionalProperties": False,
}
_TASK_MUTATIONS: tuple[
    tuple[str, Callable[[GenerationWorkerTask], GenerationWorkerTask]], ...
] = (
    ("task_id", lambda task: replace(task, task_id="changed-task")),
    (
        "task_kind",
        lambda task: replace(task, task_kind=GenerationWorkerTaskKind.EXAM_ANALYSIS),
    ),
    (
        "capability_id",
        lambda task: replace(task, capability_id=TutorCapabilityId.EXPLAIN_CONCEPT),
    ),
    (
        "capability_version",
        lambda task: replace(task, capability_version=SemanticVersion.parse("2.0.0")),
    ),
    ("manifest_fingerprint", lambda task: replace(task, manifest_fingerprint="d" * 64)),
    (
        "required_authority",
        lambda task: replace(task, required_authority=("source.read", "study:read")),
    ),
    (
        "pins",
        lambda task: replace(
            task,
            pins=replace(
                task.pins,
                model_adapter=ArtifactReference(
                    "changed-model-adapter", SemanticVersion.parse("1.0.0")
                ),
            ),
        ),
    ),
    ("definition_fingerprint", lambda task: replace(task, definition_fingerprint="d" * 64)),
    ("language", lambda task: replace(task, language="en")),
    ("preferences", lambda task: replace(task, preferences={"style": "forged"})),
    (
        "continuation_summary",
        lambda task: replace(task, continuation_summary={"changed": True}),
    ),
    ("index_references", lambda task: replace(task, index_references=("changed",))),
    (
        "evidence_references",
        lambda task: replace(task, evidence_references=("changed",)),
    ),
    ("payload", lambda task: replace(task, payload={"query": "changed"})),
    (
        "output_schema",
        lambda task: replace(
            task,
            output_schema=_CHANGED_SCHEMA,
            output_schema_fingerprint=fingerprint_output_schema(_CHANGED_SCHEMA),
        ),
    ),
    (
        "validations",
        lambda task: replace(
            task,
            expected_validations=(
                replace(task.expected_validations[0], step_id="changed-step"),
            ),
        ),
    ),
)

_RECEIPT_COMMITMENT_MUTATIONS: tuple[
    tuple[str, Callable[[GenerationWorkerReceipt], GenerationWorkerReceipt]], ...
] = (
    ("child_run", lambda receipt: replace(receipt, child_run_id=RunId("cross-wired-run"))),
    ("task", lambda receipt: replace(receipt, task_fingerprint="1" * 64)),
    ("pins", lambda receipt: replace(receipt, pins_fingerprint="2" * 64)),
    ("input", lambda receipt: replace(receipt, input_fingerprint="3" * 64)),
    ("receipt", lambda receipt: replace(receipt, validator_fingerprint="4" * 64)),
)


def _service() -> tuple[
    LessonWorkerRequest,
    _Store,
    _Resolver,
    _Binding,
    _RunningWorker,
    LessonWorkerService,
]:
    request = _request()
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    return (
        request,
        store,
        resolver,
        binding,
        worker,
        LessonWorkerService(
            store=store,
            resolver=resolver,
            task_binding=binding,
            worker=worker,
        ),
    )


def test_fixture_imports_the_exact_contract_request_and_wrapper() -> None:
    request = _request()
    wrapper = _wrapper(request)

    assert wrapper.plan_fingerprint == request.plan.plan_fingerprint
    assert wrapper.bundle_id == request.plan.bundles[0].bundle_id


def test_running_retry_reuses_prepared_scope_and_child_identity_without_resolving_again() -> None:
    request, store, resolver, binding, worker, service = _service()

    first = asyncio.run(service.start(request, _parent()))
    retry = asyncio.run(service.advance(first.run_id, request, _parent()))

    assert first == retry
    assert first.status.value == "running"
    assert resolver.calls == 1
    assert binding.calls == 1
    assert len(worker.starts) == 2
    assert worker.starts[0][0].to_bytes() == worker.starts[1][0].to_bytes()
    checkpoint = LessonWorkerCheckpoint.from_bytes(store.values[str(first.run_id)])
    assert checkpoint.pages[0].status is LessonWorkerPageStatus.CHILD_CLAIMED
    assert checkpoint.pages[0].wrapper_bytes is not None
    wrapper = PreparedPlannedFlashcardScope.from_bytes(checkpoint.pages[0].wrapper_bytes)
    assert tuple(item.topic_key for item in wrapper.prepared_scope.index) == tuple(
        item.topic_key for item in request.plan.index
    )
    active = set(request.plan.bundles[0].active_topic_keys)
    assert all(
        bool(item.evidence_handles) == (item.topic_key in active)
        for item in wrapper.prepared_scope.index
    )


def test_compact_view_and_authority_boundary_do_not_leak_private_state() -> None:
    request, _, _, _, _, service = _service()
    view = asyncio.run(service.start(request, _parent()))

    rendered = repr(view)
    assert request.query not in rendered
    assert "tutor-service" not in rendered
    assert "source.read" not in rendered
    assert not hasattr(view, "pages")
    with pytest.raises(LessonWorkerConflictError, match="authority changed"):
        asyncio.run(service.advance(view.run_id, request, _parent("other-service")))


def test_global_in_flight_cap_never_claims_a_second_running_page() -> None:
    request = _request(plan=_multi_plan(), concurrency=1)
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    view = asyncio.run(service.start(request, _parent()))
    for _ in range(3):
        view = asyncio.run(service.advance(view.run_id, request, _parent()))

    checkpoint = LessonWorkerCheckpoint.from_bytes(store.values[str(view.run_id)])
    assert tuple(page.status for page in checkpoint.pages) == (
        LessonWorkerPageStatus.CHILD_CLAIMED,
        LessonWorkerPageStatus.PENDING,
    )
    assert resolver.calls == 1
    assert binding.calls == 1
    assert {task.task_id for task, _ in worker.starts} == {
        checkpoint.pages[0].child_task_id
    }


@pytest.mark.parametrize(
    ("crash_status", "expected_binding_calls"),
    (
        (LessonWorkerPageStatus.PREPARED, 1),
        (LessonWorkerPageStatus.CHILD_CLAIMED, 1),
    ),
)
def test_retry_after_persisted_prepared_or_claimed_boundary_reuses_exact_state(
    crash_status: LessonWorkerPageStatus,
    expected_binding_calls: int,
) -> None:
    request = _request()
    store = _CrashAfterStatusStore(crash_status)
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    with pytest.raises(RuntimeError, match=f"crash after {crash_status.value}"):
        asyncio.run(service.start(request, _parent()))
    persisted = LessonWorkerCheckpoint.from_bytes(next(iter(store.values.values())))
    view = asyncio.run(service.advance(persisted.run_id, request, _parent()))

    assert view.in_progress
    assert resolver.calls == 1
    assert binding.calls == expected_binding_calls
    assert len({task.to_bytes() for task, _ in worker.starts}) <= 1


def test_retry_after_b1_terminal_before_page_cas_reuses_the_same_child() -> None:
    request = _request()
    store = _CrashBeforeStatusStore(LessonWorkerPageStatus.CHILD_TERMINAL)
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _ScriptedWorker({0: [GenerationWorkerStatus.COMPLETED]})
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    with pytest.raises(RuntimeError, match="crash before child_terminal"):
        asyncio.run(service.start(request, _parent()))
    persisted = LessonWorkerCheckpoint.from_bytes(next(iter(store.values.values())))
    assert persisted.pages[0].status is LessonWorkerPageStatus.CHILD_CLAIMED

    complete = asyncio.run(service.advance(persisted.run_id, request, _parent()))

    assert complete.completed_positions == (0,)
    assert resolver.calls == 1
    assert binding.calls == 1
    assert len(worker.tasks) == 1
    assert len(worker.starts) == 2
    retried_terminal = asyncio.run(
        service.advance(persisted.run_id, request, _parent())
    )
    assert retried_terminal == complete
    assert len(worker.starts) == 2


def test_reversed_child_completion_still_returns_canonical_plan_order() -> None:
    request = _request(plan=_multi_plan(), concurrency=2)
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _ScriptedWorker(
        {
            0: [
                GenerationWorkerStatus.RUNNING,
                GenerationWorkerStatus.RUNNING,
                GenerationWorkerStatus.COMPLETED,
            ],
            1: [GenerationWorkerStatus.RUNNING, GenerationWorkerStatus.COMPLETED],
        }
    )
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    running = asyncio.run(service.start(request, _parent()))
    reversed_partial = asyncio.run(
        service.advance(running.run_id, request, _parent())
    )
    complete = asyncio.run(
        service.advance(running.run_id, request, _parent())
    )

    assert reversed_partial.completed_positions == (1,)
    assert reversed_partial.pending_positions == (0,)
    assert reversed_partial.in_progress and reversed_partial.advance_required
    assert complete.completed_positions == (0, 1)
    assert complete.failed_positions == ()
    assert complete.pending_positions == ()
    assert (complete.candidate_count, complete.omission_count) == (3, 2)
    assert not complete.in_progress and not complete.advance_required
    checkpoint = LessonWorkerCheckpoint.from_bytes(store.values[str(complete.run_id)])
    assert tuple(page.position for page in checkpoint.pages) == (0, 1)


@pytest.mark.parametrize(
    "status",
    (
        GenerationWorkerStatus.FAILED,
        GenerationWorkerStatus.STALE,
        GenerationWorkerStatus.SUSPENDED,
    ),
)
def test_failed_stale_and_suspended_children_never_produce_success_or_detail(
    status: GenerationWorkerStatus,
) -> None:
    request = _request()
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _ScriptedWorker({0: [status]})
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    view = asyncio.run(service.start(request, _parent()))

    assert view.status.value == "failed"
    assert view.failed_positions == (0,)
    assert view.completed_positions == ()
    assert not view.in_progress and not view.advance_required
    with pytest.raises(LessonWorkerConflictError, match="detail is unavailable"):
        service.review_page(view.run_id, request, 0, _parent())


def test_verified_page_review_is_one_page_and_authority_scoped() -> None:
    request = _request()
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _ScriptedWorker({0: [GenerationWorkerStatus.COMPLETED]})
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )
    complete = asyncio.run(service.start(request, _parent()))

    reviewed = service.review_page(complete.run_id, request, 0, _parent())

    assert reviewed.page_position == 0
    assert reviewed.bundle_id == request.plan.bundles[0].bundle_id
    assert reviewed.detail.output == {"private": "candidate-body-1"}
    assert not hasattr(reviewed, "pages")
    with pytest.raises(LessonWorkerConflictError, match="authority changed"):
        service.review_page(complete.run_id, request, 0, _parent("other-service"))


def test_verified_page_result_cannot_exceed_the_request_candidate_ceiling() -> None:
    request = _request(candidate_ceiling=12)
    worker = _ScriptedWorker(
        {0: [GenerationWorkerStatus.COMPLETED]},
        counts={0: 13},
    )
    service = LessonWorkerService(
        store=_Store(),
        resolver=_Resolver(),
        task_binding=_Binding(request),
        worker=worker,
    )

    with pytest.raises(LessonWorkerConflictError, match="candidate ceiling"):
        asyncio.run(service.start(request, _parent()))


def test_identical_cas_winner_is_reloaded_without_duplicate_resolution_or_binding() -> None:
    request = _request()
    store = _WinningRaceStore()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    view = asyncio.run(service.start(request, _parent()))

    assert view.in_progress and view.advance_required
    assert resolver.calls == 1
    assert binding.calls == 1
    assert len(worker.starts) == 1


def test_conflicting_cas_winner_fails_closed_before_resolution_effect() -> None:
    request = _request()
    store = _ConflictingRaceStore()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    with pytest.raises(LessonWorkerConflictError, match="authority changed"):
        asyncio.run(service.start(request, _parent()))

    assert resolver.calls == 0
    assert binding.calls == 0
    assert worker.starts == []


def test_no_work_plan_completes_without_resolution_binding_or_worker_calls() -> None:
    request = _request(
        plan=_no_work_plan(),
        revision_commitments=(
            RevisionContentCommitment(RevisionId("rev-a"), "a" * 64),
        ),
    )
    store = _Store()
    resolver = _Resolver()
    binding = _Binding(request)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    view = asyncio.run(service.start(request, _parent()))

    assert view.status.value == "completed"
    assert not view.in_progress and not view.advance_required
    assert view.completed_positions == view.failed_positions == view.pending_positions == ()
    assert resolver.calls == 0
    assert binding.calls == 0
    assert worker.starts == []


@pytest.mark.parametrize(("field", "mutation"), _TASK_MUTATIONS)
def test_every_returned_b1_task_field_is_verified_before_delegation(
    field: str,
    mutation: Callable[[GenerationWorkerTask], GenerationWorkerTask],
) -> None:
    request = _request()
    store = _Store()
    resolver = _Resolver()
    binding = _MutatingBinding(request, mutation)
    worker = _RunningWorker()
    service = LessonWorkerService(
        store=store,
        resolver=resolver,
        task_binding=binding,
        worker=worker,
    )

    with pytest.raises(LessonWorkerConflictError, match="changed worker task"):
        asyncio.run(service.start(request, _parent()))

    assert binding.calls == 1, field
    assert worker.starts == [], field


@pytest.mark.parametrize(("commitment", "mutation"), _RECEIPT_COMMITMENT_MUTATIONS)
def test_cross_wired_child_detail_fails_before_terminal_page_persistence(
    commitment: str,
    mutation: Callable[[GenerationWorkerReceipt], GenerationWorkerReceipt],
) -> None:
    request = _request()
    store = _Store()
    worker = _MutatingDetailWorker(mutation)
    service = LessonWorkerService(
        store=store,
        resolver=_Resolver(),
        task_binding=_Binding(request),
        worker=worker,
    )

    with pytest.raises(LessonWorkerConflictError, match="completed child receipt changed"):
        asyncio.run(service.start(request, _parent()))

    checkpoint = LessonWorkerCheckpoint.from_bytes(next(iter(store.values.values())))
    assert checkpoint.pages[0].status is LessonWorkerPageStatus.CHILD_CLAIMED, commitment
    assert checkpoint.pages[0].receipt is None, commitment


@pytest.mark.parametrize(("commitment", "mutation"), _RECEIPT_COMMITMENT_MUTATIONS)
def test_cross_wired_child_detail_fails_closed_during_page_review(
    commitment: str,
    mutation: Callable[[GenerationWorkerReceipt], GenerationWorkerReceipt],
) -> None:
    request = _request()
    worker = _ScriptedWorker({0: [GenerationWorkerStatus.COMPLETED]})
    service = LessonWorkerService(
        store=_Store(),
        resolver=_Resolver(),
        task_binding=_Binding(request),
        worker=worker,
    )
    complete = asyncio.run(service.start(request, _parent()))
    task_id = worker.starts[0]
    original = worker.results[task_id]
    worker.results[task_id] = replace(
        original,
        detail=WorkerDetailView(mutation(original.detail.receipt), original.detail.output),
    )

    with pytest.raises(LessonWorkerConflictError, match="completed child receipt changed"):
        service.review_page(complete.run_id, request, 0, _parent())
