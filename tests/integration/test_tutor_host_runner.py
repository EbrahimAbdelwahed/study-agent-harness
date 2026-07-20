from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from study_agent.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    SuspendedCapabilityOutcome,
    TerminatedCapabilityOutcome,
    TutorCapabilityId,
)
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RunId,
    SessionId,
)
from study_agent.hosts import (
    AdvertisedCapability,
    AnswerDialogueDecision,
    HostActionIdentity,
    PendingContinuationDescriptor,
    ScriptedTutorDecisionPort,
    StartCapabilityDecision,
    TutorContinuationRecord,
    TutorHostContext,
    TutorHostLimits,
    TutorHostRunner,
    TutorHostRunStatus,
)
from study_agent.playbooks import (
    PlaybookRunStatus,
    ToolBehaviorPin,
    ValidationOutcome,
    ValidatorDisposition,
    VerifiedRunRecord,
    VersionPins,
)
from study_agent.skills import ArtifactReference, SemanticVersion

SHA_A = "a" * 64


class _Token:
    def is_interrupted(self) -> bool:
        return False


class _Assembler:
    def assemble(self, *args: object, **kwargs: object) -> TutorHostContext:
        del args, kwargs
        return TutorHostContext(
            "course",
            "session",
            1,
            1,
            {},
            {},
            (
                AdvertisedCapability(
                    "explain_concept",
                    "explain_concept@1",
                    SHA_A,
                    {
                        "type": "object",
                        "properties": {"topic": {"type": "string"}},
                        "required": ("topic",),
                        "additionalProperties": False,
                    },
                    False,
                ),
            ),
        )


class _Gateway:
    def __init__(self) -> None:
        self.starts = 0

    def discover(self) -> tuple[object, ...]:
        return ()

    async def start(self, *args: object) -> object:
        self.starts += 1
        return FailedCapabilityOutcome(RunId("run-1"), "failed safely")

    async def resume(self, *args: object) -> object:
        raise AssertionError("resume is not part of this start turn")


class _Authority:
    def create_context(
        self,
        course_id: CourseId,
        session_id: SessionId,
        capability_id: TutorCapabilityId,
        action_identity: HostActionIdentity,
    ) -> ExecutionContext:
        del capability_id
        return ExecutionContext(
            PrincipalKind.SERVICE,
            "host",
            course_id,
            CorrelationId("correlation"),
            frozenset({"study:explain"}),
            session_id,
            idempotency_key=action_identity.value,
        )


class _Identity:
    def issue(
        self,
        host_turn_id: str,
        context_fingerprint: str,
        decision_fingerprint: str,
        decision_generation: int,
    ) -> HostActionIdentity:
        return HostActionIdentity(
            f"{host_turn_id}:{context_fingerprint}:{decision_fingerprint}:{decision_generation}"
        )


class _Store:
    def create(self, *args: object) -> bool:
        raise AssertionError("failed start does not suspend")

    def load(self, *args: object) -> object:
        raise AssertionError("failed start has no continuation")

    def delete(self, *args: object) -> None:
        raise AssertionError("failed start has no continuation")


class _BytesStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], bytes] = {}

    def create(
        self, course: CourseId, session: SessionId, fingerprint: str, payload: bytes
    ) -> bool:
        key = (str(course), str(session), fingerprint)
        if key in self.values:
            return self.values[key] == payload
        self.values[key] = payload
        return True

    def load(self, course: CourseId, session: SessionId, fingerprint: str) -> bytes:
        return self.values[(str(course), str(session), fingerprint)]

    def delete(self, course: CourseId, session: SessionId, fingerprint: str) -> None:
        self.values.pop((str(course), str(session), fingerprint), None)


class _BoundaryToken:
    def __init__(self, stage: str | None = None) -> None:
        self.stage = stage
        self.interrupted = False

    def is_interrupted(self) -> bool:
        return self.interrupted

    def mark(self, stage: str) -> None:
        if self.stage == stage:
            self.interrupted = True


class _BoundaryAssembler(_Assembler):
    def __init__(self, token: _BoundaryToken) -> None:
        self.token = token
        self.calls = 0

    def assemble(self, *args: object, **kwargs: object) -> TutorHostContext:
        self.calls += 1
        value = super().assemble(*args, **kwargs)
        self.token.mark("assemble")
        return value


class _BoundaryDecision:
    def __init__(self, token: _BoundaryToken, decision: object) -> None:
        self.token = token
        self.decision = decision
        self.calls = 0

    async def decide(self, context: TutorHostContext, interruption: _BoundaryToken) -> object:
        del context, interruption
        self.calls += 1
        self.token.mark("decide")
        return self.decision


class _BoundaryIdentity(_Identity):
    def __init__(self, token: _BoundaryToken) -> None:
        self.token = token
        self.calls = 0
        self.generations: list[int] = []

    def issue(
        self,
        host_turn_id: str,
        context_fingerprint: str,
        decision_fingerprint: str,
        decision_generation: int,
    ) -> HostActionIdentity:
        self.calls += 1
        self.generations.append(decision_generation)
        identity = super().issue(
            host_turn_id, context_fingerprint, decision_fingerprint, decision_generation
        )
        self.token.mark("identity")
        return identity


class _BoundaryAuthority(_Authority):
    def __init__(self, token: _BoundaryToken) -> None:
        self.token = token
        self.calls = 0

    def create_context(
        self,
        course_id: CourseId,
        session_id: SessionId,
        capability_id: TutorCapabilityId,
        action_identity: HostActionIdentity,
    ) -> ExecutionContext:
        self.calls += 1
        value = super().create_context(course_id, session_id, capability_id, action_identity)
        self.token.mark("authority")
        return value


class _BoundaryStartGateway(_Gateway):
    def __init__(self, token: _BoundaryToken) -> None:
        super().__init__()
        self.token = token

    async def start(self, *args: object) -> object:
        value = await super().start(*args)
        self.token.mark("start")
        return value


class _BoundaryStore(_BytesStore):
    def __init__(self, token: _BoundaryToken) -> None:
        super().__init__()
        self.token = token
        self.loads = 0
        self.creates = 0
        self.deletes = 0

    def create(
        self, course: CourseId, session: SessionId, fingerprint: str, payload: bytes
    ) -> bool:
        self.creates += 1
        value = super().create(course, session, fingerprint, payload)
        self.token.mark("store_create")
        return value

    def load(self, course: CourseId, session: SessionId, fingerprint: str) -> bytes:
        self.loads += 1
        value = super().load(course, session, fingerprint)
        self.token.mark("store_load")
        return value

    def delete(self, course: CourseId, session: SessionId, fingerprint: str) -> None:
        self.deletes += 1
        super().delete(course, session, fingerprint)
        self.token.mark("store_delete")


class _SuspendingGateway:
    def __init__(self, continuation: CapabilityContinuation) -> None:
        self.continuation = continuation
        self.starts = 0
        self.resumes = 0

    def discover(self) -> tuple[object, ...]:
        return ()

    async def start(self, *args: object) -> SuspendedCapabilityOutcome:
        self.starts += 1
        return SuspendedCapabilityOutcome(
            self.continuation.run_id,
            "Confirm the answer.",
            self.continuation,
            {"type": "boolean"},
        )

    async def resume(self, *args: object) -> CompletedCapabilityOutcome:
        self.resumes += 1
        version = self.continuation.pins
        run = VerifiedRunRecord(
            self.continuation.run_id,
            self.continuation.definition_fingerprint,
            self.continuation.inputs,
            version,
            self.continuation.read_dependencies,
            {"answer": "done"},
            (),
            PlaybookRunStatus.COMPLETED,
        )
        return CompletedCapabilityOutcome(run, {"answer": "done"})


class _BoundaryResumeGateway(_SuspendingGateway):
    def __init__(self, continuation: CapabilityContinuation, token: _BoundaryToken) -> None:
        super().__init__(continuation)
        self.token = token

    async def resume(self, *args: object) -> CompletedCapabilityOutcome:
        value = await super().resume(*args)
        self.token.mark("resume")
        return value


class _OutcomeGateway(_Gateway):
    def __init__(self, outcome: object = None, error: BaseException | None = None) -> None:
        super().__init__()
        self.outcome = outcome
        self.error = error

    async def start(self, *args: object) -> object:
        self.starts += 1
        if self.error is not None:
            raise self.error
        return self.outcome


class _StaleStartGateway(_Gateway):
    def __init__(self, stale_count: int) -> None:
        super().__init__()
        self.stale_count = stale_count

    async def start(self, *args: object) -> object:
        self.starts += 1
        if self.starts <= self.stale_count:
            return StaleCapabilityOutcome(RunId("run-1"), "stale detail")
        return FailedCapabilityOutcome(RunId("run-1"), "failed safely")


class _StaleResumeGateway(_StaleStartGateway):
    def __init__(self) -> None:
        super().__init__(0)
        self.resumes = 0

    async def resume(self, *args: object) -> object:
        self.resumes += 1
        return StaleCapabilityOutcome(RunId("run-1"), "stale detail")


class _IdempotentGateway(_Gateway):
    def __init__(self, continuation: CapabilityContinuation, token: _BoundaryToken) -> None:
        super().__init__()
        self.continuation = continuation
        self.token = token
        self.logical_start: set[str] = set()
        self.logical_resume: set[str] = set()
        self.start_calls = 0
        self.resume_calls = 0

    async def start(self, *args: object) -> CompletedCapabilityOutcome:
        self.start_calls += 1
        context = args[2]
        assert isinstance(context, ExecutionContext)
        key = context.idempotency_key
        assert key is not None
        self.logical_start.add(key)
        value = _completed()
        self.token.mark("start")
        return value

    async def resume(self, *args: object) -> CompletedCapabilityOutcome:
        self.resume_calls += 1
        context = args[2]
        assert isinstance(context, ExecutionContext)
        key = context.idempotency_key
        assert key is not None
        self.logical_resume.add(key)
        value = _completed()
        self.token.mark("resume")
        return value


class _InProgressGateway(_Gateway):
    async def start(self, *args: object) -> object:
        self.starts += 1
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.IN_PROGRESS,
            "private progress detail",
            retryable=True,
        )


def test_in_progress_is_distinct_and_exact_retry_keeps_identity() -> None:
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    gateway = _InProgressGateway()
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    first = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert first.status is TutorHostRunStatus.IN_PROGRESS
    assert first.retry_receipt is not None
    second = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    retried = asyncio.run(
        second.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            _Token(),
            retry_receipt=first.retry_receipt,
        )
    )
    assert retried.status is TutorHostRunStatus.IN_PROGRESS
    assert retried.retry_receipt is not None
    assert (
        retried.retry_receipt.action_identity_fingerprint
        == first.retry_receipt.action_identity_fingerprint
    )
    assert gateway.starts == 2


def _continuation() -> CapabilityContinuation:
    version = SemanticVersion.parse("1.0.0")
    pins = VersionPins(
        ArtifactReference("skill", version),
        ArtifactReference("playbook", version),
        ArtifactReference("prompt", version),
        (ToolBehaviorPin("tool", version),),
        ArtifactReference("model", version),
        ArtifactReference("state", version),
    )
    return CapabilityContinuation(
        RunId("run-1"),
        TutorCapabilityId.EXPLAIN_CONCEPT,
        version,
        SHA_A,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 64,
        "confirm",
        1,
        {"topic": "valves"},
        pins,
        (),
    )


def _completed() -> CompletedCapabilityOutcome:
    continuation = _continuation()
    run = VerifiedRunRecord(
        continuation.run_id,
        continuation.definition_fingerprint,
        continuation.inputs,
        continuation.pins,
        continuation.read_dependencies,
        {"answer": "done"},
        (),
        PlaybookRunStatus.COMPLETED,
    )
    return CompletedCapabilityOutcome(run, {"answer": "done"})


def _terminated() -> TerminatedCapabilityOutcome:
    run = _completed().run
    return TerminatedCapabilityOutcome(
        replace(
            run,
            status=PlaybookRunStatus.TERMINATED,
            termination=ValidationOutcome(
                False,
                ValidatorDisposition.TERMINATE,
                {},
                "stopped",
            ),
        )
    )


@pytest.mark.parametrize(
    ("outcome", "status"),
    (
        (_completed(), TutorHostRunStatus.COMPLETED),
        (_terminated(), TutorHostRunStatus.TERMINATED),
        (CancelledCapabilityOutcome(RunId("run-1"), "private"), TutorHostRunStatus.CANCELLED),
        (FailedCapabilityOutcome(RunId("run-1"), "private"), TutorHostRunStatus.FAILED),
    ),
)
def test_terminal_outcome_table_maps_closed_status_without_detail_leakage(
    outcome: object, status: TutorHostRunStatus
) -> None:
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        _OutcomeGateway(outcome),  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert result.status is status
    assert result.learner_text is None
    if status is not TutorHostRunStatus.COMPLETED:
        assert result.completed_output is None


@pytest.mark.parametrize(
    "code",
    (
        CapabilityGatewayErrorCode.INVALID_REQUEST,
        CapabilityGatewayErrorCode.UNAUTHORIZED,
        CapabilityGatewayErrorCode.NOT_FOUND,
        CapabilityGatewayErrorCode.CONFLICT,
        CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
    ),
)
def test_non_in_progress_gateway_errors_fail_closed(code: CapabilityGatewayErrorCode) -> None:
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    error = CapabilityGatewayError(code, "sensitive authority detail")
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        _OutcomeGateway(error=error),  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert result.status is TutorHostRunStatus.FAILED
    assert result.learner_text is None
    assert result.completed_output is None


def test_stale_start_reassembles_and_issues_new_generation() -> None:
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    gateway = _StaleStartGateway(1)
    identity = _BoundaryIdentity(_BoundaryToken())
    assembler = _BoundaryAssembler(_BoundaryToken())
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(
            ((context.fingerprint, decision), (context.fingerprint, decision))
        ),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        identity,
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(2, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert result.status is TutorHostRunStatus.FAILED
    assert assembler.calls == 2
    assert identity.generations == [1, 2]
    assert gateway.starts == 2


def test_stale_budget_exhaustion_never_replays_decision() -> None:
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    gateway = _StaleStartGateway(2)
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(
            ((context.fingerprint, decision), (context.fingerprint, decision))
        ),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(2, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert result.status is TutorHostRunStatus.BUDGET_EXHAUSTED
    assert gateway.starts == 2


def test_stale_resume_deletes_old_continuation_and_refreshes_generation() -> None:
    continuation = _continuation()
    store = _BytesStore()
    descriptor = _seed_record(store, continuation)
    assembler = _PendingAssembler()
    pending_context = assembler.assemble(
        CourseId("course"), SessionId("session"), pending_continuation=descriptor
    )
    start_context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    answer = AnswerDialogueDecision(descriptor.fingerprint, True)
    start = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    gateway = _StaleResumeGateway()
    identity = _BoundaryIdentity(_BoundaryToken())
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(
            ((pending_context.fingerprint, answer), (start_context.fingerprint, start))
        ),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        identity,
        store,
        TutorHostLimits(2, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    result = asyncio.run(
        runner.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            _Token(),
            pending_fingerprint=descriptor.fingerprint,
        )
    )
    assert result.status is TutorHostRunStatus.FAILED
    assert gateway.resumes == 1
    assert gateway.starts == 1
    assert identity.generations == [1, 2]
    assert not store.values


@pytest.mark.parametrize("case", ("missing", "forged", "cross_course", "cross_session"))
def test_pending_selection_rejects_missing_forged_and_cross_owner_records(case: str) -> None:
    continuation = _continuation()
    store = _BytesStore()
    fingerprint = continuation.fingerprint
    if case == "forged":
        store.values[("course", "session", fingerprint)] = b'{"schema_version":1}'
    elif case == "cross_course":
        descriptor = _seed_record(store, continuation, CourseId("other"))
        store.values[("course", "session", fingerprint)] = store.values.pop(
            ("other", "session", descriptor.fingerprint)
        )
    elif case == "cross_session":
        descriptor = _seed_record(store, continuation, session=SessionId("other"))
        store.values[("course", "session", fingerprint)] = store.values.pop(
            ("course", "other", descriptor.fingerprint)
        )
    gateway = _StaleResumeGateway()
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(()),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        store,
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_PendingAssembler(),  # type: ignore[arg-type]
    )
    pending = fingerprint if case != "missing" else "f" * 64
    result = asyncio.run(
        runner.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            _Token(),
            pending_fingerprint=pending,
        )
    )
    assert result.status is TutorHostRunStatus.FAILED
    assert gateway.resumes == 0
    assert gateway.starts == 0


class _PendingAssembler(_Assembler):
    def assemble(self, *args: object, **kwargs: object) -> TutorHostContext:
        pending = kwargs.get("pending_continuation")
        base = super().assemble(*args, **kwargs)
        if isinstance(pending, PendingContinuationDescriptor):
            return TutorHostContext(
                base.course_id,
                base.session_id,
                base.tutor_snapshot_sequence,
                base.learner_evidence_through_sequence,
                base.tutor_snapshot,
                base.learner_evidence,
                base.advertised_capabilities,
                pending,
            )
        return base


def test_public_runner_path_maps_gateway_failure_without_leaking_message() -> None:
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    context = _Assembler().assemble(CourseId("course"), SessionId("session"))
    gateway = _Gateway()
    runner = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=_Assembler(),  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert result.status is TutorHostRunStatus.FAILED
    assert result.completed_output is None
    assert result.learner_text is None
    assert gateway.starts == 1


def test_suspend_persists_bytes_and_new_runner_resumes_exact_context() -> None:
    continuation = _continuation()
    gateway = _SuspendingGateway(continuation)
    store = _BytesStore()
    assembler = _PendingAssembler()
    first_context = assembler.assemble(CourseId("course"), SessionId("session"))
    start = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    first = TutorHostRunner(
        ScriptedTutorDecisionPort(((first_context.fingerprint, start),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        store,
        TutorHostLimits(1, 2, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    suspended = asyncio.run(first.run(CourseId("course"), SessionId("session"), "turn-1", _Token()))
    assert suspended.status is TutorHostRunStatus.SUSPENDED
    assert suspended.pending_continuation is not None
    fingerprint = suspended.pending_continuation.fingerprint
    assert len(store.values) == 1
    pending_context = assembler.assemble(
        CourseId("course"),
        SessionId("session"),
        pending_continuation=suspended.pending_continuation,
    )
    answer = AnswerDialogueDecision(fingerprint, True)
    second = TutorHostRunner(
        ScriptedTutorDecisionPort(((pending_context.fingerprint, answer),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        store,
        TutorHostLimits(1, 2, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    completed = asyncio.run(
        second.run(
            CourseId("course"),
            SessionId("session"),
            "turn-2",
            _Token(),
            pending_fingerprint=fingerprint,
        )
    )
    assert completed.status is TutorHostRunStatus.COMPLETED
    assert completed.completed_output == {"answer": "done"}
    assert gateway.starts == 1
    assert gateway.resumes == 1
    assert not store.values


def test_lost_output_start_retry_reuses_receipt_and_one_logical_execution() -> None:
    continuation = _continuation()
    token = _BoundaryToken("start")
    gateway = _IdempotentGateway(continuation, token)
    assembler = _Assembler()
    context = assembler.assemble(CourseId("course"), SessionId("session"))
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    first = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    interrupted = asyncio.run(first.run(CourseId("course"), SessionId("session"), "turn-1", token))
    assert interrupted.status is TutorHostRunStatus.INTERRUPTED
    assert interrupted.retry_receipt is not None
    retry = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        _Store(),  # type: ignore[arg-type]
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    completed = asyncio.run(
        retry.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            _Token(),
            retry_receipt=interrupted.retry_receipt,
        )
    )
    assert completed.status is TutorHostRunStatus.COMPLETED
    assert gateway.start_calls == 2
    assert len(gateway.logical_start) == 1
    mismatched = asyncio.run(
        retry.run(
            CourseId("course"),
            SessionId("session"),
            "other-turn",
            _Token(),
            retry_receipt=interrupted.retry_receipt,
        )
    )
    assert mismatched.status is TutorHostRunStatus.FAILED
    assert gateway.start_calls == 2


def test_lost_output_resume_retry_preserves_continuation_and_one_logical_execution() -> None:
    continuation = _continuation()
    store = _BytesStore()
    descriptor = _seed_record(store, continuation)
    assembler = _PendingAssembler()
    context = assembler.assemble(
        CourseId("course"), SessionId("session"), pending_continuation=descriptor
    )
    decision = AnswerDialogueDecision(descriptor.fingerprint, True)
    token = _BoundaryToken("resume")
    gateway = _IdempotentGateway(continuation, token)
    first = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        store,
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    interrupted = asyncio.run(
        first.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            token,
            pending_fingerprint=descriptor.fingerprint,
        )
    )
    assert interrupted.status is TutorHostRunStatus.INTERRUPTED
    assert interrupted.retry_receipt is not None
    assert interrupted.pending_continuation is not None
    retry = TutorHostRunner(
        ScriptedTutorDecisionPort(((context.fingerprint, decision),)),
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _Authority(),
        _Identity(),
        store,
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    completed = asyncio.run(
        retry.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            _Token(),
            retry_receipt=interrupted.retry_receipt,
            pending_fingerprint=descriptor.fingerprint,
        )
    )
    assert completed.status is TutorHostRunStatus.COMPLETED
    assert gateway.resume_calls == 2
    assert len(gateway.logical_resume) == 1
    mismatched = asyncio.run(
        retry.run(
            CourseId("course"),
            SessionId("session"),
            "other-turn",
            _Token(),
            retry_receipt=interrupted.retry_receipt,
            pending_fingerprint=descriptor.fingerprint,
        )
    )
    assert mismatched.status is TutorHostRunStatus.FAILED
    assert gateway.resume_calls == 2


@pytest.mark.parametrize("stage", ("assemble", "decide", "identity", "authority", "start"))
def test_interruption_after_each_start_effect_stops_later_effects(stage: str) -> None:
    token = _BoundaryToken(stage)
    decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
    adapter = _BoundaryDecision(token, decision)
    assembler = _BoundaryAssembler(token)
    identity = _BoundaryIdentity(token)
    authority = _BoundaryAuthority(token)
    gateway = _BoundaryStartGateway(token)
    runner = TutorHostRunner(
        adapter,  # type: ignore[arg-type]
        None,
        None,
        gateway,  # type: ignore[arg-type]
        authority,
        identity,
        _BytesStore(),
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    adapter.decision = decision
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", token))
    assert result.status is TutorHostRunStatus.INTERRUPTED
    assert result.completed_output is None
    assert gateway.starts == (1 if stage == "start" else 0)


def test_interruption_before_assemble_has_zero_effects() -> None:
    token = _BoundaryToken()
    token.interrupted = True
    assembler = _BoundaryAssembler(token)
    gateway = _BoundaryStartGateway(token)
    runner = TutorHostRunner(
        _BoundaryDecision(token, StartCapabilityDecision("explain_concept", {"topic": "valves"})),  # type: ignore[arg-type]
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _BoundaryAuthority(token),
        _BoundaryIdentity(token),
        _BytesStore(),
        TutorHostLimits(1, 1, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    result = asyncio.run(runner.run(CourseId("course"), SessionId("session"), "turn-1", token))
    assert result.status is TutorHostRunStatus.INTERRUPTED
    assert assembler.calls == 0
    assert gateway.starts == 0


def _seed_record(
    store: _BytesStore,
    continuation: CapabilityContinuation,
    course: CourseId | None = None,
    session: SessionId | None = None,
) -> PendingContinuationDescriptor:
    course = CourseId("course") if course is None else course
    session = SessionId("session") if session is None else session
    descriptor = PendingContinuationDescriptor(
        continuation.fingerprint,
        "explain_concept@1",
        continuation.dialogue_step_id,
        "Confirm the answer.",
        {"type": "boolean"},
    )
    execution = _Authority().create_context(
        course, session, TutorCapabilityId.EXPLAIN_CONCEPT, HostActionIdentity("seed")
    )
    record = TutorContinuationRecord(continuation, execution, descriptor)
    store.create(course, session, descriptor.fingerprint, record.to_bytes())
    return descriptor


@pytest.mark.parametrize("stage", ("store_load", "store_create", "store_delete", "resume"))
def test_interruption_store_and_resume_effects_never_expose_output(stage: str) -> None:
    continuation = _continuation()
    token = _BoundaryToken(stage)
    store = _BoundaryStore(token)
    assembler = _PendingAssembler()
    if stage == "store_create":
        initial = _Assembler().assemble(CourseId("course"), SessionId("session"))
        start_decision = StartCapabilityDecision("explain_concept", {"topic": "valves"})
        gateway = _SuspendingGateway(continuation)
        start_adapter = ScriptedTutorDecisionPort(((initial.fingerprint, start_decision),))
        runner_adapter: object = start_adapter
        pending_fingerprint = None
    else:
        descriptor = _seed_record(store, continuation)
        token.interrupted = False
        answer_decision: object = AnswerDialogueDecision(descriptor.fingerprint, True)
        answer_adapter: object = _BoundaryDecision(token, answer_decision)
        runner_adapter = answer_adapter
        gateway = _BoundaryResumeGateway(continuation, token)
        pending_fingerprint = descriptor.fingerprint
    runner = TutorHostRunner(
        runner_adapter,  # type: ignore[arg-type]
        None,
        None,
        gateway,  # type: ignore[arg-type]
        _BoundaryAuthority(token),
        _BoundaryIdentity(token),
        store,
        TutorHostLimits(1, 2, 1, 128),
        context_assembler=assembler,  # type: ignore[arg-type]
    )
    result = asyncio.run(
        runner.run(
            CourseId("course"),
            SessionId("session"),
            "turn-1",
            token,
            pending_fingerprint=pending_fingerprint,
        )
    )
    assert result.status is TutorHostRunStatus.INTERRUPTED
    assert result.completed_output is None
