"""One explicit async runtime over existing PF-06/PF-07 services."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from study_agent.api.authority import AuthorityContext
from study_agent.application.errors import translate_exception
from study_agent.artifacts.service import (
    ArtifactConflictError,
    ArtifactService,
    RetryableArtifactConflictError,
)
from study_agent.assessments.service import (
    AssessmentConflictError,
    AssessmentService,
    RetryableAssessmentConflictError,
)
from study_agent.capabilities.contracts import CapabilityManifest, CapabilityOutcome
from study_agent.domain._validation import JsonValue
from study_agent.domain.authority import CancellationOutcome
from study_agent.domain.context import ExecutionContext
from study_agent.domain.errors import (
    ConflictFailure,
    HarnessError,
    StaleFailure,
    UnauthorizedFailure,
    ValidationFailure,
)
from study_agent.domain.events import PrincipalKind
from study_agent.domain.identifiers import CorrelationId, CourseId, EventId, SessionId
from study_agent.kernel.module import KernelModule, KernelModuleRegistry
from study_agent.ports.storage import CourseStreamHighWaterPort, EventStore
from study_agent.recall.service import (
    RecallConflictError,
    RecallService,
    RetryableRecallConflictError,
)
from study_agent.state.projection import replay

if TYPE_CHECKING:
    from study_agent.api.runtime import (
        ArtifactDecisionRequest,
        AssessmentObservationRequest,
        CapabilityResumeRequest,
        CapabilityStartRequest,
        CommitReceipt,
        RecallReviewRequest,
        RuntimeDependencies,
        RuntimeSnapshot,
    )

_T = TypeVar("_T")
_COMMAND_CONFLICTS = (
    ArtifactConflictError,
    AssessmentConflictError,
    RecallConflictError,
)
_RETRYABLE_COMMAND_CONFLICTS = (
    RetryableArtifactConflictError,
    RetryableAssessmentConflictError,
    RetryableRecallConflictError,
)


class _CapabilityPort(Protocol):
    def discover(self) -> Sequence[CapabilityManifest]: ...

    async def start_request(
        self,
        request: object,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome: ...

    async def resume(
        self,
        continuation: object,
        response: object,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome: ...


@dataclass(frozen=True, slots=True)
class _Bindings:
    capabilities: _CapabilityPort
    artifacts: ArtifactService
    assessments: AssessmentService
    recall: RecallService


def _bindings(dependencies: RuntimeDependencies, modules: tuple[KernelModule, ...]) -> _Bindings:
    services: dict[str, object] = {}
    allowed = {"capabilities", "artifacts", "assessments", "recall"}
    for module in modules:
        if not isinstance(module, KernelModule):
            raise ValidationFailure("modules must contain KernelModule values")
        for name, service in module.services:
            if name not in allowed:
                raise ValidationFailure(f"unsupported runtime service {name!r}")
            if name in services:
                raise ValidationFailure(f"duplicate runtime service {name!r}")
            services[name] = service
    missing = allowed.difference(services)
    if missing:
        raise ValidationFailure("runtime services are incomplete: " + ", ".join(sorted(missing)))
    capabilities = services["capabilities"]
    capability_methods = ("discover", "start_request", "resume")
    if not all(callable(getattr(capabilities, name, None)) for name in capability_methods):
        raise ValidationFailure("capabilities service is incompatible")
    artifacts = services["artifacts"]
    assessments = services["assessments"]
    recall = services["recall"]
    if not isinstance(artifacts, ArtifactService):
        raise ValidationFailure("artifacts service is incompatible")
    if not isinstance(assessments, AssessmentService):
        raise ValidationFailure("assessments service is incompatible")
    if not isinstance(recall, RecallService):
        raise ValidationFailure("recall service is incompatible")
    for name, service in (
        ("artifacts", artifacts),
        ("assessments", assessments),
        ("recall", recall),
    ):
        if getattr(service, "_events", None) is not dependencies.storage:
            raise ValidationFailure(f"{name} service uses a different event store")
    return _Bindings(cast(_CapabilityPort, capabilities), artifacts, assessments, recall)


def _validate_dependencies(dependencies: RuntimeDependencies) -> None:
    from study_agent.api.runtime import RuntimeDependencies

    if not isinstance(dependencies, RuntimeDependencies):
        raise ValidationFailure("dependencies must be RuntimeDependencies")
    if dependencies.repository.event_store is not dependencies.storage:
        raise ValidationFailure("repository and storage must be the same object")
    if not isinstance(dependencies.storage, CourseStreamHighWaterPort):
        raise ValidationFailure("storage must expose bounded stream high-water")
    if not callable(getattr(dependencies.repository, "close", None)):
        raise ValidationFailure("repository must expose close()")
    required_methods = (
        (dependencies.clock, ("now",)),
        (dependencies.id_factory, ("new",)),
        (dependencies.model_adapter, ("generate", "stream", "cancel")),
        (dependencies.policy, ("authorize",)),
    )
    for owner, methods in required_methods:
        if not all(callable(getattr(owner, method, None)) for method in methods):
            raise ValidationFailure("runtime dependency is incompatible")
    if getattr(dependencies.model_adapter, "capabilities", None) is None:
        raise ValidationFailure("model adapter capabilities are required")


def _context(
    dependencies: RuntimeDependencies,
    course_id: CourseId,
    session_id: SessionId,
    authority: AuthorityContext,
    correlation_id: CorrelationId,
    idempotency_key: str,
) -> ExecutionContext:
    if authority.principal is not dependencies.principal:
        raise UnauthorizedFailure("authority belongs to another Host")
    if authority.session_id != str(session_id):
        raise UnauthorizedFailure("authority session does not match request")
    return ExecutionContext(
        authority.principal.kind,
        authority.principal.principal_id,
        course_id,
        correlation_id,
        frozenset(grant.name for grant in authority.grants),
        session_id,
        None,
        idempotency_key,
    )


def _cancelled(callback: Callable[[], bool] | None) -> bool:
    if callback is None:
        return False
    if not callable(callback):
        raise ValidationFailure("cancellation must be callable")
    return bool(callback())


def _high_water(storage: EventStore, course_id: CourseId) -> int:
    port = cast(CourseStreamHighWaterPort, storage)
    try:
        return port.observe_high_water(course_id).sequence
    except HarnessError:
        raise
    except BaseException as error:
        raise translate_exception(error) from error


def _preflight(storage: EventStore, course_id: CourseId, expected: int) -> None:
    actual = _high_water(storage, course_id)
    if actual != expected:
        raise StaleFailure(
            "the durable stream changed before operation",
            details={"expected": expected, "actual": actual},
        )


def _receipt(
    storage: EventStore,
    operation: str,
    course_id: CourseId,
    expected: int,
    observed_before: int,
    idempotency_key: str,
    result: object,
) -> CommitReceipt:
    from study_agent.api.runtime import CommitReceipt

    final = _high_water(storage, course_id)
    if final < expected:
        raise StaleFailure("the durable stream moved backwards")
    try:
        records = tuple(storage.read(course_id, after_sequence=observed_before))
    except HarnessError:
        raise
    except BaseException as error:
        raise translate_exception(error) from error
    expected_sequences = tuple(range(observed_before + 1, final + 1))
    actual_sequences = tuple(record.stream_sequence for record in records)
    if actual_sequences != expected_sequences:
        raise StaleFailure("the committed event delta is not contiguous")
    result_sequence = getattr(result, "sequence", None)
    if result_sequence is None:
        result_sequence = getattr(result, "event_sequence", None)
    if result_sequence is not None and result_sequence != final:
        raise StaleFailure("the command result does not match the durable stream")
    ids = tuple(EventId(str(item.event_id)) for item in records)
    identity = getattr(result, "id", None)
    payload: dict[str, JsonValue] = {"stream_sequence": final}
    if identity is not None:
        payload["record_id"] = str(identity)
    return CommitReceipt(
        operation,
        course_id,
        final,
        ids,
        idempotency_key,
        final == observed_before,
        payload,
    )


def _durable_high_water(storage: EventStore, course_id: CourseId, expected: int) -> int:
    """Capture the command boundary while permitting a canonical exact retry."""

    actual = _high_water(storage, course_id)
    if actual < expected:
        raise StaleFailure(
            "the durable stream is behind the requested high-water mark",
            details={"expected": expected, "actual": actual},
        )
    return actual


def _translate_command_error(error: BaseException, correlation_id: CorrelationId) -> HarnessError:
    if isinstance(error, _COMMAND_CONFLICTS):
        return ConflictFailure(
            "command input conflicts with canonical history",
            correlation_id=correlation_id,
        )
    if isinstance(error, _RETRYABLE_COMMAND_CONFLICTS):
        return StaleFailure(
            "the durable stream changed before commit",
            correlation_id=correlation_id,
        )
    return translate_exception(error, correlation_id=correlation_id)


class AsyncStudyAgentRuntime:
    __slots__ = ("_active", "_bindings", "_dependencies", "_event_registry", "_lock", "_state")

    def __init__(
        self,
        dependencies: RuntimeDependencies,
        bindings: _Bindings,
        event_registry: object,
    ) -> None:
        self._dependencies = dependencies
        self._bindings = bindings
        self._event_registry = event_registry
        self._lock = RLock()
        self._active = 0
        self._state = "OPEN"

    @asynccontextmanager
    async def _operation(self) -> Any:
        with self._lock:
            if self._state != "OPEN":
                raise ValidationFailure("runtime is closed")
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    def _authorize(self, operation: str, authority: AuthorityContext, *, durable: bool) -> None:
        if not isinstance(authority, AuthorityContext):
            raise UnauthorizedFailure("authority context is invalid")
        if authority.principal is not self._dependencies.principal:
            raise UnauthorizedFailure("authority belongs to another Host")
        if durable and authority.principal.kind is PrincipalKind.MODEL:
            raise UnauthorizedFailure("MODEL cannot commit durable effects")
        try:
            self._dependencies.policy.authorize(operation, authority, durable=durable)
        except HarnessError:
            raise
        except BaseException as error:
            raise translate_exception(
                error,
                correlation_id=authority.correlation_id,
            ) from error

    async def discover_capabilities(
        self, authority: AuthorityContext, correlation_id: CorrelationId
    ) -> tuple[CapabilityManifest, ...]:
        async with self._operation():
            self._authorize("runtime.discover_capabilities", authority, durable=False)
            if not isinstance(correlation_id, CorrelationId):
                raise ValidationFailure("correlation_id must be CorrelationId")
            try:
                manifests = tuple(self._bindings.capabilities.discover())
                if not all(isinstance(item, CapabilityManifest) for item in manifests):
                    raise ValidationFailure("capability discovery returned invalid manifests")
                return tuple(sorted(manifests, key=lambda item: item.identity))
            except HarnessError:
                raise
            except BaseException as error:
                raise translate_exception(error, correlation_id=correlation_id) from error

    async def read_snapshot(
        self,
        course_id: CourseId,
        authority: AuthorityContext,
        correlation_id: CorrelationId,
        *,
        expected_stream_high_water: int | None = None,
    ) -> RuntimeSnapshot:
        from study_agent.api.runtime import RuntimeSnapshot

        async with self._operation():
            self._authorize("runtime.read_snapshot", authority, durable=False)
            try:
                records = tuple(self._dependencies.storage.read(course_id))
                projection = replay(course_id, records, cast(Any, self._event_registry))
            except HarnessError:
                raise
            except BaseException as error:
                raise translate_exception(error, correlation_id=correlation_id) from error
            if (
                expected_stream_high_water is not None
                and projection.sequence != expected_stream_high_water
            ):
                raise StaleFailure("the durable stream changed before read")
            return RuntimeSnapshot(
                course_id,
                projection.sequence,
                projection.state,
                sha256(projection.canonical_bytes()).hexdigest(),
            )

    async def start_capability(
        self,
        request: CapabilityStartRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        async with self._operation():
            authority = request.capability.authority
            self._authorize("capability.start", authority, durable=True)
            _preflight(
                self._dependencies.storage,
                request.course_id,
                request.capability.expected_stream_high_water,
            )
            context = _context(
                self._dependencies,
                request.course_id,
                request.session_id,
                authority,
                CorrelationId(str(request.capability.correlation_id)),
                request.capability.idempotency_key,
            )
            return await self._bindings.capabilities.start_request(
                request.capability, context, cancellation=cancellation
            )

    async def resume_capability(
        self,
        request: CapabilityResumeRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        async with self._operation():
            self._authorize("capability.resume", request.authority, durable=True)
            _preflight(
                self._dependencies.storage,
                request.course_id,
                request.expected_stream_high_water,
            )
            context = _context(
                self._dependencies,
                request.course_id,
                request.session_id,
                request.authority,
                request.correlation_id,
                request.idempotency_key,
            )
            return await self._bindings.capabilities.resume(
                request.continuation,
                request.response,
                context,
                cancellation=cancellation,
            )

    async def record_artifact_decision(
        self,
        request: ArtifactDecisionRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        async with self._operation():
            self._authorize("artifact.record_decision", request.authority, durable=True)
            if _cancelled(cancellation):
                return CancellationOutcome.before_commit(correlation_id=request.correlation_id)
            observed_before = _durable_high_water(
                self._dependencies.storage,
                request.course_id,
                request.expected_stream_high_water,
            )
            context = _context(
                self._dependencies,
                request.course_id,
                request.session_id,
                request.authority,
                request.correlation_id,
                request.idempotency_key,
            )
            try:
                if request.authority.principal.kind is PrincipalKind.HUMAN:
                    if request.decision is None:
                        raise ValidationFailure("HUMAN decision requires an outcome")
                    result = self._bindings.artifacts.record_human_decision(
                        request.artifact_revision_id,
                        request.decision,
                        request.supersedes_revision_id,
                        context,
                        request.expected_stream_high_water,
                    )
                elif request.authority.principal.kind is PrincipalKind.SERVICE:
                    if request.decision is not None or request.supersedes_revision_id is not None:
                        raise ValidationFailure("SERVICE decision outcome is policy-owned")
                    result = self._bindings.artifacts.apply_service_decision(
                        request.artifact_revision_id,
                        context,
                        request.expected_stream_high_water,
                    )
                else:
                    raise UnauthorizedFailure("MODEL cannot decide artifacts")
                return _receipt(
                    self._dependencies.storage,
                    "artifact.record_decision",
                    request.course_id,
                    request.expected_stream_high_water,
                    observed_before,
                    request.idempotency_key,
                    result,
                )
            except HarnessError:
                raise
            except BaseException as error:
                raise _translate_command_error(
                    error,
                    request.correlation_id,
                ) from error

    async def record_assessment_observation(
        self,
        request: AssessmentObservationRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        async with self._operation():
            self._authorize("assessment.record_observation", request.authority, durable=True)
            if _cancelled(cancellation):
                return CancellationOutcome.before_commit(correlation_id=request.correlation_id)
            observed_before = _durable_high_water(
                self._dependencies.storage,
                request.course_id,
                request.expected_stream_high_water,
            )
            context = _context(
                self._dependencies,
                request.course_id,
                request.session_id,
                request.authority,
                request.correlation_id,
                request.idempotency_key,
            )
            try:
                result = self._bindings.assessments.record_verified_grade(
                    request.run_id,
                    context,
                    request.expected_stream_high_water,
                    supersedes_grade_id=request.supersedes_grade_id,
                )
                return _receipt(
                    self._dependencies.storage,
                    "assessment.record_observation",
                    request.course_id,
                    request.expected_stream_high_water,
                    observed_before,
                    request.idempotency_key,
                    result,
                )
            except HarnessError:
                raise
            except BaseException as error:
                raise _translate_command_error(
                    error,
                    request.correlation_id,
                ) from error

    async def review_recall(
        self,
        request: RecallReviewRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        async with self._operation():
            self._authorize("recall.review", request.authority, durable=True)
            if _cancelled(cancellation):
                return CancellationOutcome.before_commit(correlation_id=request.correlation_id)
            observed_before = _durable_high_water(
                self._dependencies.storage,
                request.course_id,
                request.expected_stream_high_water,
            )
            context = _context(
                self._dependencies,
                request.course_id,
                request.session_id,
                request.authority,
                request.correlation_id,
                request.idempotency_key,
            )
            try:
                result = self._bindings.recall.review(
                    request.revision_id,
                    request.rating,
                    context,
                    request.expected_stream_high_water,
                    latency_ms=request.latency_ms,
                    confidence_bps=request.confidence_bps,
                )
                return _receipt(
                    self._dependencies.storage,
                    "recall.review",
                    request.course_id,
                    request.expected_stream_high_water,
                    observed_before,
                    request.idempotency_key,
                    result,
                )
            except HarnessError:
                raise
            except BaseException as error:
                raise _translate_command_error(
                    error,
                    request.correlation_id,
                ) from error

    async def close(self) -> None:
        with self._lock:
            if self._state == "CLOSED":
                return
            owner = self._state == "OPEN"
            if owner:
                self._state = "CLOSING"
        if not owner:
            while True:
                with self._lock:
                    if self._state == "CLOSED":
                        return
                await asyncio.sleep(0)
        while True:
            with self._lock:
                if self._active == 0:
                    break
            await asyncio.sleep(0)
        try:
            self._dependencies.repository.close()
        finally:
            with self._lock:
                self._state = "CLOSED"


class SyncStudyAgentRuntime:
    __slots__ = ("_async_runtime",)

    def __init__(self, runtime: AsyncStudyAgentRuntime) -> None:
        if not isinstance(runtime, AsyncStudyAgentRuntime):
            raise ValidationFailure("sync facade requires AsyncStudyAgentRuntime")
        self._async_runtime = runtime

    @property
    def async_runtime(self) -> AsyncStudyAgentRuntime:
        return self._async_runtime

    @staticmethod
    def _run(coroutine: Coroutine[Any, Any, _T]) -> _T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        coroutine.close()
        raise RuntimeError(
            "SyncStudyAgentRuntime cannot run inside an active event loop; "
            "use AsyncStudyAgentRuntime"
        )

    def discover_capabilities(
        self,
        authority: AuthorityContext,
        correlation_id: CorrelationId,
    ) -> tuple[CapabilityManifest, ...]:
        return self._run(self._async_runtime.discover_capabilities(authority, correlation_id))

    def read_snapshot(
        self,
        course_id: CourseId,
        authority: AuthorityContext,
        correlation_id: CorrelationId,
        *,
        expected_stream_high_water: int | None = None,
    ) -> RuntimeSnapshot:
        return self._run(
            self._async_runtime.read_snapshot(
                course_id,
                authority,
                correlation_id,
                expected_stream_high_water=expected_stream_high_water,
            )
        )

    def start_capability(
        self,
        request: CapabilityStartRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        return self._run(
            self._async_runtime.start_capability(
                request,
                cancellation=cancellation,
            )
        )

    def resume_capability(
        self,
        request: CapabilityResumeRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        return self._run(
            self._async_runtime.resume_capability(
                request,
                cancellation=cancellation,
            )
        )

    def record_artifact_decision(
        self,
        request: ArtifactDecisionRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        return self._run(
            self._async_runtime.record_artifact_decision(
                request,
                cancellation=cancellation,
            )
        )

    def record_assessment_observation(
        self,
        request: AssessmentObservationRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        return self._run(
            self._async_runtime.record_assessment_observation(
                request,
                cancellation=cancellation,
            )
        )

    def review_recall(
        self,
        request: RecallReviewRequest,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CommitReceipt | CancellationOutcome:
        return self._run(
            self._async_runtime.review_recall(
                request,
                cancellation=cancellation,
            )
        )

    def close(self) -> None:
        self._run(self._async_runtime.close())


def create_runtime(
    dependencies: RuntimeDependencies,
    modules: tuple[KernelModule, ...] = (),
) -> AsyncStudyAgentRuntime:
    _validate_dependencies(dependencies)
    registry = KernelModuleRegistry()
    for module in tuple(modules):
        registry.register(module)
    registry.close()
    snapshot = registry.compile()
    return AsyncStudyAgentRuntime(
        dependencies,
        _bindings(dependencies, tuple(modules)),
        snapshot._event_registry(),
    )


__all__ = ("AsyncStudyAgentRuntime", "SyncStudyAgentRuntime", "create_runtime")
