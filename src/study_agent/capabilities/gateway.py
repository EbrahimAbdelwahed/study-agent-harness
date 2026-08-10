"""Authority-bound lifecycle gateway over trusted playbook checkpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from hashlib import sha256
from typing import NoReturn, Protocol, cast

from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.domain.authority import AuthorityContext
from study_agent.playbooks import (
    DialogueStep,
    EngineErrorCode,
    InspectedRunRecord,
    PlaybookEngine,
    PlaybookEngineError,
    PlaybookRunStatus,
    ReadDependency,
    RunStatus,
    StepTraceStatus,
    VersionPins,
    playbook_definition_fingerprint,
)
from study_agent.skills import ArtifactReference
from study_agent.tools.schema import SchemaValidationError, validate_json

from .bindings import CapabilityBinding, ProfiledCapabilityBinding
from .contracts import (
    CancelledCapabilityOutcome,
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CapabilityIdentifier,
    CapabilityManifest,
    CapabilityOutcome,
    CapabilityRequest,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    SuspendedCapabilityOutcome,
    TerminatedCapabilityOutcome,
    TutorCapabilityId,
)
from .registry import StudyCapabilityRegistry

_AUTHORITY_DEPENDENCY_KIND = "capability.authority"
_STREAM_HIGH_WATER_DEPENDENCY_KIND = "capability.stream"


class CapabilityHighWaterResolver(Protocol):
    def __call__(self, *, context: ExecutionContext, inputs: JsonObject) -> int: ...


class StudyCapabilityGateway:
    """Execute only the capability explicitly selected by a trusted host."""

    def __init__(
        self,
        *,
        bindings: tuple[CapabilityBinding, ...],
        engine: PlaybookEngine,
        stream_high_water_resolver: CapabilityHighWaterResolver | None = None,
    ) -> None:
        values = tuple(bindings)
        if not values:
            raise ValueError("capability gateway requires at least one trusted binding")
        if not all(isinstance(item, CapabilityBinding) for item in values):
            raise TypeError("capability gateway bindings must use CapabilityBinding")
        if not isinstance(engine, PlaybookEngine):
            raise TypeError("capability gateway engine must be PlaybookEngine")
        ids = tuple(item.manifest.id for item in values)
        if len(set(ids)) != len(ids):
            raise ValueError("capability gateway bindings must be unique by id")
        self._bindings = {item.manifest.id: item for item in values}
        self._registry = StudyCapabilityRegistry(tuple(item.manifest for item in values))
        self._engine = engine
        if stream_high_water_resolver is not None and not callable(
            stream_high_water_resolver
        ):
            raise TypeError("stream_high_water_resolver must be callable")
        self._stream_high_water_resolver = stream_high_water_resolver

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return self._registry.discover()

    async def start(
        self,
        capability_id: CapabilityIdentifier | CapabilityRequest,
        inputs: JsonObject | None = None,
        context: ExecutionContext | None = None,
    ) -> CapabilityOutcome:
        if isinstance(capability_id, CapabilityRequest):
            if inputs is not None:
                raise TypeError("CapabilityRequest start does not accept positional inputs")
            return await self.start_request(capability_id, context=context)
        if inputs is None or context is None:
            raise TypeError("capability start requires inputs and ExecutionContext")
        binding = self._binding(capability_id)
        return await self._start_bound(binding, inputs, inputs, context)

    async def start_request(
        self,
        request: CapabilityRequest,
        *,
        context: ExecutionContext | None = None,
    ) -> CapabilityOutcome:
        """Execute one canonical request after binding its opaque authority.

        The legacy three-argument ``start`` form remains available for existing
        hosts.  Requests carry the public manifest identity and host-issued
        authority, so this path resolves by exact manifest identity and never
        accepts an ordinal or provider-selected implementation.
        """

        if not isinstance(request, CapabilityRequest):
            raise TypeError("capability request must be CapabilityRequest")
        binding = self._binding_identity(request.manifest_identity)
        execution_context = _request_context(request, context)
        return await self._start_bound(
            binding,
            request.inputs,
            request.inputs,
            execution_context,
            expected_stream_high_water=request.expected_stream_high_water,
        )

    async def _start_bound(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        public_inputs: JsonObject,
        execution_inputs: JsonObject,
        context: ExecutionContext,
        *,
        expected_stream_high_water: int | None = None,
    ) -> CapabilityOutcome:
        authority, retry = self._authorize(binding, context)
        try:
            frozen_public_inputs = freeze_object(public_inputs)
            frozen_inputs = freeze_object(execution_inputs)
            validate_json(frozen_public_inputs, binding.manifest.input_schema)
        except (SchemaValidationError, ValueError, TypeError) as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "capability inputs violate the manifest schema",
            ) from error
        run_id = _run_id(binding, authority, retry)

        inspected = self._inspect_optional(binding, run_id)
        if inspected is not None:
            self._require_start_retry(
                binding,
                inspected,
                frozen_inputs,
                authority,
                expected_stream_high_water,
            )
            return self._observed(binding, inspected, authority, retry)

        dependencies = _dependencies(
            binding,
            context,
            frozen_public_inputs,
            authority=authority,
            expected_stream_high_water=expected_stream_high_water,
        )
        if expected_stream_high_water is not None:
            stale = self._check_stream_high_water(
                run_id,
                context,
                frozen_public_inputs,
                expected_stream_high_water,
                dependencies,
            )
            if stale is not None:
                return stale
        try:
            await self._engine.execute(
                run_id=run_id,
                skill=binding.skill,
                definition=binding.playbook,
                inputs=frozen_inputs,
                pins=binding.pins,
                read_dependencies=dependencies,
            )
        except asyncio.CancelledError:
            committed = self._observe_after_host_cancellation(
                binding, run_id, authority, retry
            )
            if committed is not None:
                return committed
            raise
        except PlaybookEngineError as error:
            if error.failure.code is EngineErrorCode.DUPLICATE_RUN:
                inspected = self._inspect_required(binding, run_id)
                self._require_start_retry(
                    binding,
                    inspected,
                    frozen_inputs,
                    authority,
                    expected_stream_high_water,
                )
                if inspected.read_dependencies != dependencies:
                    return StaleCapabilityOutcome(
                        run_id, "capability read dependencies changed since start"
                    )
                return self._observed(binding, inspected, authority, retry)
            return self._engine_error(run_id, error)
        inspected = self._inspect_required(binding, run_id)
        return self._observed(binding, inspected, authority, retry)

    async def resume(
        self,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
    ) -> CapabilityOutcome:
        if not isinstance(continuation, CapabilityContinuation):
            raise TypeError("continuation must be CapabilityContinuation")
        binding = self._binding(continuation.capability_id)
        return await self._resume_bound(binding, continuation, response, context)

    async def _resume_bound(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
    ) -> CapabilityOutcome:
        authority, retry = self._authorize(binding, context)
        self._require_continuation_authority(binding, continuation, authority, retry)
        inspected = self._inspect_required(binding, continuation.run_id)
        self._require_continuation_bindings(binding, continuation, inspected)
        try:
            frozen_response = freeze_json(response)
        except (TypeError, ValueError) as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "capability response is not valid JSON",
            ) from error
        dialogue = binding.playbook.steps[continuation.next_step_index - 1]
        if not isinstance(dialogue, DialogueStep):
            self._conflict("continuation dialogue identity differs from the playbook")
        try:
            validate_json(frozen_response, dialogue.response_schema.value)
        except SchemaValidationError as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "capability response violates the dialogue schema",
            ) from error

        if inspected.status is not RunStatus.SUSPENDED:
            self._require_persisted_resume(
                binding, continuation, inspected, frozen_response
            )
            return self._observed(binding, inspected, authority, retry)

        if (
            inspected.checkpoint_fingerprint != continuation.checkpoint_fingerprint
            or inspected.dialogue_step_id != continuation.dialogue_step_id
            or inspected.next_step_index != continuation.next_step_index
        ):
            self._conflict("continuation does not identify the suspended generation")
        dependencies = _dependencies(
            binding,
            context,
            _public_input_projection(binding, continuation.inputs),
            authority=authority,
            expected_stream_high_water=_expected_stream_high_water(
                continuation.read_dependencies
            ),
        )
        expected_stream_high_water = _expected_stream_high_water(
            continuation.read_dependencies
        )
        if expected_stream_high_water is not None:
            stale = self._check_stream_high_water(
                continuation.run_id,
                context,
                _public_input_projection(binding, continuation.inputs),
                expected_stream_high_water,
                dependencies,
            )
            if stale is not None:
                return stale
        try:
            await self._engine.resume(
                run_id=continuation.run_id,
                skill=binding.skill,
                definition=binding.playbook,
                inputs=continuation.inputs,
                pins=binding.pins,
                read_dependencies=dependencies,
                resume_input=frozen_response,
            )
        except PlaybookEngineError as error:
            if error.failure.code is EngineErrorCode.STALE_READ_DEPENDENCY:
                return StaleCapabilityOutcome(
                    continuation.run_id,
                    "capability read dependencies changed before resume",
                )
            if error.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT:
                raced = self._inspect_required(binding, continuation.run_id)
                self._require_continuation_bindings(binding, continuation, raced)
                self._require_persisted_resume(
                    binding, continuation, raced, frozen_response
                )
                return self._observed(binding, raced, authority, retry)
            return self._engine_error(continuation.run_id, error)
        except asyncio.CancelledError:
            committed = self._observe_after_host_cancellation(
                binding, continuation.run_id, authority, retry
            )
            if committed is not None:
                return committed
            raise
        inspected = self._inspect_required(binding, continuation.run_id)
        self._require_persisted_resume(binding, continuation, inspected, frozen_response)
        return self._observed(binding, inspected, authority, retry)

    def _binding(self, capability_id: CapabilityIdentifier) -> CapabilityBinding:
        if not isinstance(capability_id, (TutorCapabilityId, str)):
            raise TypeError("capability id must use a CapabilityIdentifier")
        try:
            return self._bindings[capability_id]
        except KeyError as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "capability is not registered",
            ) from error

    def _binding_identity(self, manifest_identity: str) -> CapabilityBinding:
        if not isinstance(manifest_identity, str) or not manifest_identity.strip():
            raise TypeError("capability manifest identity must be non-empty text")
        try:
            manifest = self._registry.get_identity(manifest_identity)
        except (KeyError, TypeError) as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "capability manifest is not registered",
            ) from error
        binding = self._bindings[manifest.id]
        if binding.manifest.identity != manifest_identity:
            self._conflict("capability manifest identity is not the trusted binding")
        return binding

    def _authorize(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        context: ExecutionContext,
    ) -> tuple[str, str]:
        if not isinstance(context, ExecutionContext):
            raise TypeError("capability context must be ExecutionContext")
        if not isinstance(context.course_id, CourseId):
            raise TypeError("capability context course_id must be CourseId")
        if context.session_id is not None and not isinstance(
            context.session_id, SessionId
        ):
            raise TypeError("capability context session_id must be SessionId")
        if not isinstance(context.principal_kind, PrincipalKind):
            raise TypeError("capability context principal_kind must be PrincipalKind")
        if context.principal_kind not in {PrincipalKind.HUMAN, PrincipalKind.SERVICE}:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "capability authority must be a trusted human or service",
            )
        if context.session_id is None or context.idempotency_key is None:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "capability execution requires session and idempotency identity",
            )
        if not set(binding.manifest.required_authority) <= context.requested_capabilities:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "required capability authority was not granted",
            )
        authority = _fingerprint(
            "study-agent-capability-authority-v1",
            {
                "principal_kind": context.principal_kind.value,
                "principal_id": context.principal_id,
                "course_id": str(context.course_id),
                "session_id": str(context.session_id),
                "grants": tuple(sorted(context.requested_capabilities)),
            },
        )
        retry = _fingerprint(
            "study-agent-capability-retry-v1",
            {"idempotency_key": context.idempotency_key},
        )
        return authority, retry

    def _inspect_optional(
        self, binding: CapabilityBinding | ProfiledCapabilityBinding, run_id: RunId
    ) -> InspectedRunRecord | None:
        try:
            return self._engine.inspect(run_id=run_id, definition=binding.playbook)
        except PlaybookEngineError as error:
            if error.failure.code is EngineErrorCode.CHECKPOINT_NOT_FOUND:
                return None
            if error.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT:
                raise CapabilityGatewayError(
                    CapabilityGatewayErrorCode.CONFLICT,
                    "persisted capability slot differs from the trusted binding",
                ) from error
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
                "capability checkpoint could not be inspected safely",
            ) from error

    def _probe_bound(
        self,
        binding: ProfiledCapabilityBinding,
        run_id: RunId,
    ) -> tuple[InspectedRunRecord | None, EngineErrorCode | None]:
        """Inspect one closed definition without executing effects or mapping ownership."""

        try:
            return self._engine.inspect(run_id=run_id, definition=binding.playbook), None
        except PlaybookEngineError as error:
            if error.failure.code in {
                EngineErrorCode.CHECKPOINT_NOT_FOUND,
                EngineErrorCode.INCOMPATIBLE_CHECKPOINT,
            }:
                return None, error.failure.code
            return None, EngineErrorCode.INCOMPATIBLE_CHECKPOINT

    def _inspect_required(
        self, binding: CapabilityBinding | ProfiledCapabilityBinding, run_id: RunId
    ) -> InspectedRunRecord:
        inspected = self._inspect_optional(binding, run_id)
        if inspected is None:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "capability checkpoint was not found",
            )
        return inspected

    def _require_start_retry(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        inspected: InspectedRunRecord,
        inputs: JsonObject,
        authority: str,
        expected_stream_high_water: int | None,
    ) -> None:
        if inspected.definition_fingerprint != playbook_definition_fingerprint(
            binding.playbook
        ):
            self._conflict("persisted capability definition differs from trusted binding")
        if _json_identity_fingerprint(inspected.inputs) != _json_identity_fingerprint(inputs):
            self._conflict("idempotency identity was reused with different inputs")
        if _pins_payload(inspected.pins) != _pins_payload(binding.pins):
            self._conflict("persisted capability pins differ from the trusted binding")
        persisted_authority = _metadata_dependency(
            inspected.read_dependencies, _AUTHORITY_DEPENDENCY_KIND
        )
        if persisted_authority is not None and persisted_authority.version != authority:
            self._conflict("idempotency identity was reused with another authority")
        if expected_stream_high_water is not None:
            persisted_high_water = _metadata_dependency(
                inspected.read_dependencies, _STREAM_HIGH_WATER_DEPENDENCY_KIND
            )
            if (
                persisted_high_water is None
                or persisted_high_water.version != str(expected_stream_high_water)
            ):
                self._conflict(
                    "idempotency identity was reused with another stream high-water mark"
                )

    def _require_continuation_authority(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        authority: str,
        retry: str,
    ) -> None:
        expected_run = _run_id(binding, authority, retry)
        if (
            continuation.capability_id != binding.manifest.id
            or continuation.run_id != expected_run
            or continuation.capability_version != binding.manifest.version
            or continuation.manifest_fingerprint != binding.manifest_fingerprint
            or continuation.authority_fingerprint != authority
            or continuation.retry_identity_fingerprint != retry
        ):
            self._conflict("continuation authority or capability binding changed")

    def _require_continuation_bindings(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        inspected: InspectedRunRecord,
    ) -> None:
        if (
            continuation.definition_fingerprint != inspected.definition_fingerprint
            or inspected.definition_fingerprint
            != playbook_definition_fingerprint(binding.playbook)
            or _json_identity_fingerprint(continuation.inputs)
            != _json_identity_fingerprint(inspected.inputs)
            or _pins_payload(continuation.pins) != _pins_payload(inspected.pins)
            or continuation.read_dependencies != inspected.read_dependencies
            or _pins_payload(inspected.pins) != _pins_payload(binding.pins)
        ):
            self._conflict("continuation bindings differ from the persisted run")
        index = continuation.next_step_index - 1
        if index < 0 or index >= len(binding.playbook.steps):
            self._conflict("continuation dialogue index is invalid")
        step = binding.playbook.steps[index]
        if step.id != continuation.dialogue_step_id or step.kind != "dialogue":
            self._conflict("continuation dialogue identity differs from the playbook")

    def _require_persisted_resume(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        inspected: InspectedRunRecord,
        response: JsonValue,
    ) -> None:
        step = binding.playbook.steps[continuation.next_step_index - 1]
        if step.output_key not in inspected.outputs or _json_identity_fingerprint(
            inspected.outputs[step.output_key]
        ) != _json_identity_fingerprint(response):
            self._conflict("dialogue retry response differs from the persisted response")
        matching = tuple(
            trace
            for trace in inspected.traces
            if trace.step_id == continuation.dialogue_step_id
            and trace.status is StepTraceStatus.COMPLETED
            and trace.details.get("resume_generation_fingerprint")
            == continuation.checkpoint_fingerprint
        )
        if len(matching) != 1:
            self._conflict("persisted dialogue response claimed another generation")

    def _observed(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        inspected: InspectedRunRecord,
        authority: str,
        retry: str,
    ) -> CapabilityOutcome:
        if inspected.status is RunStatus.RUNNING:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.IN_PROGRESS,
                "capability execution is still in progress",
                retryable=True,
            )
        if inspected.status is RunStatus.SUSPENDED:
            assert inspected.dialogue_step_id is not None
            assert inspected.dialogue_request is not None
            continuation = CapabilityContinuation(
                run_id=inspected.run_id,
                capability_id=binding.manifest.id,
                capability_version=binding.manifest.version,
                manifest_fingerprint=binding.manifest_fingerprint,
                authority_fingerprint=authority,
                retry_identity_fingerprint=retry,
                definition_fingerprint=inspected.definition_fingerprint,
                checkpoint_fingerprint=inspected.checkpoint_fingerprint,
                dialogue_step_id=inspected.dialogue_step_id,
                next_step_index=inspected.next_step_index,
                inputs=inspected.inputs,
                pins=inspected.pins,
                read_dependencies=inspected.read_dependencies,
            )
            dialogue = binding.playbook.steps[continuation.next_step_index - 1]
            if not isinstance(dialogue, DialogueStep):
                self._conflict("continuation dialogue identity differs from the playbook")
            return SuspendedCapabilityOutcome(
                inspected.run_id,
                inspected.dialogue_request,
                continuation,
                dialogue.response_schema.value,
            )
        if inspected.status is RunStatus.CANCELLED:
            return CancelledCapabilityOutcome(
                inspected.run_id, "capability execution was cancelled by the model transport"
            )
        if inspected.status is RunStatus.FAILED:
            return FailedCapabilityOutcome(
                inspected.run_id, "capability execution failed safely"
            )
        try:
            run = self._engine.recover(
                run_id=inspected.run_id,
                definition=binding.playbook,
                inputs=inspected.inputs,
                pins=inspected.pins,
                read_dependencies=inspected.read_dependencies,
            )
        except PlaybookEngineError as error:
            return self._engine_error(inspected.run_id, error)
        if run.status is PlaybookRunStatus.TERMINATED:
            return cast(CapabilityOutcome, TerminatedCapabilityOutcome(run))
        if binding.output_key not in run.outputs:
            return FailedCapabilityOutcome(
                inspected.run_id, "verified capability output is missing"
            )
        output = run.outputs[binding.output_key]
        try:
            validate_json(output, binding.manifest.output_schema)
        except (SchemaValidationError, ValueError, TypeError):
            return FailedCapabilityOutcome(
                inspected.run_id, "verified capability output violates its manifest"
            )
        return CompletedCapabilityOutcome(run, output)

    @staticmethod
    def _engine_error(run_id: RunId, error: PlaybookEngineError) -> CapabilityOutcome:
        if error.failure.code is EngineErrorCode.STALE_READ_DEPENDENCY:
            return StaleCapabilityOutcome(run_id, "capability read dependencies are stale")
        if error.failure.code is EngineErrorCode.CANCELLED:
            return CancelledCapabilityOutcome(run_id, "capability execution was cancelled")
        return FailedCapabilityOutcome(run_id, "capability execution failed safely")

    def _observe_after_host_cancellation(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        run_id: RunId,
        authority: str,
        retry: str,
    ) -> CapabilityOutcome | None:
        """Return a committed result, but preserve an ambiguous pre-CAS cancel.

        ``PlaybookEngine`` owns the checkpoint CAS.  A host task cancellation
        can race the await boundary on either side of that CAS.  A RUNNING
        checkpoint is deliberately left ambiguous and the cancellation is
        re-raised; a non-running checkpoint is already durable and can be
        observed without replaying effects.
        """

        try:
            inspected = self._engine.inspect(run_id=run_id, definition=binding.playbook)
        except PlaybookEngineError:
            return None
        if inspected.status is RunStatus.RUNNING:
            return None
        return self._observed(binding, inspected, authority, retry)

    def _check_stream_high_water(
        self,
        run_id: RunId,
        context: ExecutionContext,
        inputs: JsonObject,
        expected: int,
        dependencies: tuple[ReadDependency, ...],
    ) -> StaleCapabilityOutcome | None:
        actual = self._stream_high_water(context, inputs, dependencies)
        if actual != expected:
            return StaleCapabilityOutcome(
                run_id,
                "capability stream high-water changed before execution",
            )
        return None

    def _stream_high_water(
        self,
        context: ExecutionContext,
        inputs: JsonObject,
        dependencies: tuple[ReadDependency, ...],
    ) -> int:
        if self._stream_high_water_resolver is not None:
            try:
                actual = self._stream_high_water_resolver(context=context, inputs=inputs)
            except Exception as error:
                raise CapabilityGatewayError(
                    CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
                    "capability stream high-water could not be read safely",
                ) from error
            if type(actual) is not int or actual < 0:
                raise CapabilityGatewayError(
                    CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
                    "capability stream high-water resolver returned an invalid value",
                )
            return actual
        inferred = _inferred_high_water(dependencies)
        if inferred is None:
            # A request at the empty stream origin is safe when a host has no
            # stream adapter to consult. Any later mark must be verified by an
            # injected resolver rather than guessed.
            if _metadata_dependency(
                dependencies, _STREAM_HIGH_WATER_DEPENDENCY_KIND
            ) is not None:
                expected = _metadata_dependency(
                    dependencies, _STREAM_HIGH_WATER_DEPENDENCY_KIND
                )
                assert expected is not None
                if expected.version != "0":
                    raise CapabilityGatewayError(
                        CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
                        "capability stream high-water requires a host resolver",
                    )
            return 0
        return inferred

    @staticmethod
    def _conflict(message: str) -> NoReturn:
        raise CapabilityGatewayError(CapabilityGatewayErrorCode.CONFLICT, message)


def _dependencies(
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    context: ExecutionContext,
    inputs: JsonObject,
    *,
    authority: str,
    expected_stream_high_water: int | None,
) -> tuple[ReadDependency, ...]:
    try:
        dependencies = tuple(
            binding.dependency_resolver(context=context, inputs=inputs)
        )
    except Exception as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependency resolver failed safely",
        ) from error
    if not all(isinstance(item, ReadDependency) for item in dependencies):
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependency resolver returned invalid values",
        )
    metadata = [
        ReadDependency(_AUTHORITY_DEPENDENCY_KIND, binding.manifest.identity, authority)
    ]
    if expected_stream_high_water is not None:
        metadata.append(
            ReadDependency(
                _STREAM_HIGH_WATER_DEPENDENCY_KIND,
                str(context.course_id),
                str(expected_stream_high_water),
            )
        )
    combined = (*dependencies, *metadata)
    keys = tuple((item.kind, item.id) for item in combined)
    if len(set(keys)) != len(keys):
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependency resolver returned duplicate identities",
        )
    return combined


def _request_context(
    request: CapabilityRequest, context: ExecutionContext | None
) -> ExecutionContext:
    authority = request.authority
    if not isinstance(authority, AuthorityContext):
        raise TypeError("capability request authority must be AuthorityContext")
    if authority.principal_kind not in {PrincipalKind.HUMAN, PrincipalKind.SERVICE}:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.UNAUTHORIZED,
            "capability authority must be a trusted human or service",
        )
    grants = frozenset(grant.name for grant in authority.grants)
    correlation_id = (
        request.correlation_id
        if isinstance(request.correlation_id, CorrelationId)
        else CorrelationId(request.correlation_id)
    )
    session_id = (
        None if authority.session_id is None else SessionId(authority.session_id)
    )
    if context is not None:
        if not isinstance(context, ExecutionContext):
            raise TypeError("capability request context must be ExecutionContext")
        scoped_courses = {
            scope.name.removeprefix("course:")
            for scope in authority.scopes
            if scope.name.startswith("course:")
        }
        if (
            context.principal_kind is not authority.principal_kind
            or context.principal_id != authority.principal_id
            or context.requested_capabilities != grants
            or context.session_id != session_id
            or context.correlation_id != correlation_id
            or context.idempotency_key != request.idempotency_key
            or (scoped_courses and str(context.course_id) not in scoped_courses)
        ):
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "capability request authority does not match the execution context",
            )
        return context

    course_scopes = tuple(
        scope.name.removeprefix("course:")
        for scope in authority.scopes
        if scope.name.startswith("course:")
    )
    if len(course_scopes) != 1 or not course_scopes[0]:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INVALID_REQUEST,
            "capability request authority must identify one course scope",
        )
    if session_id is None:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INVALID_REQUEST,
            "capability request authority must identify a session",
        )
    return ExecutionContext(
        authority.principal_kind,
        authority.principal_id,
        CourseId(course_scopes[0]),
        correlation_id,
        grants,
        session_id,
        idempotency_key=request.idempotency_key,
    )


def _metadata_dependency(
    dependencies: tuple[ReadDependency, ...], kind: str
) -> ReadDependency | None:
    matches = tuple(item for item in dependencies if item.kind == kind)
    if len(matches) > 1:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability checkpoint contains duplicate gateway metadata",
        )
    return matches[0] if matches else None


def _expected_stream_high_water(
    dependencies: tuple[ReadDependency, ...],
) -> int | None:
    metadata = _metadata_dependency(dependencies, _STREAM_HIGH_WATER_DEPENDENCY_KIND)
    if metadata is None:
        return None
    try:
        value = int(metadata.version)
    except ValueError as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability checkpoint contains an invalid stream high-water mark",
        ) from error
    if value < 0 or str(value) != metadata.version:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability checkpoint contains an invalid stream high-water mark",
        )
    return value


def _inferred_high_water(dependencies: tuple[ReadDependency, ...]) -> int | None:
    candidates: list[int] = []
    for dependency in dependencies:
        if dependency.kind not in {"course", "stream", "event_stream"}:
            continue
        prefix = "sequence-"
        if not dependency.version.startswith(prefix):
            continue
        try:
            value = int(dependency.version.removeprefix(prefix))
        except ValueError:
            continue
        if value >= 0:
            candidates.append(value)
    if not candidates:
        return None
    if len(set(candidates)) != 1:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependencies contain conflicting stream high-water marks",
        )
    return candidates[0]


def _public_input_projection(
    binding: CapabilityBinding | ProfiledCapabilityBinding, inputs: JsonObject
) -> JsonObject:
    properties = binding.manifest.input_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability manifest has no public input projection",
        )
    try:
        projected = freeze_object({key: inputs[key] for key in properties})
        validate_json(projected, binding.manifest.input_schema)
    except (KeyError, SchemaValidationError, TypeError, ValueError) as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.CONFLICT,
            "persisted capability inputs lost their public projection",
        ) from error
    return projected


def _run_id(
    binding: CapabilityBinding | ProfiledCapabilityBinding, authority: str, retry: str
) -> RunId:
    del authority
    digest = _fingerprint(
        "study-agent-capability-run-v1",
        {
            # The run store is the idempotency slot.  All request material
            # other than the capability identity and host key is checked
            # against the persisted checkpoint after this slot is found.
            "capability_id": binding.manifest.id.value,
            "retry_identity_fingerprint": retry,
        },
    )
    return RunId(f"capability-run-sha256:{digest}")


def _pins_payload(pins: VersionPins) -> tuple[object, ...]:
    def artifact(reference: ArtifactReference) -> tuple[str, str]:
        return reference.id, str(reference.version)

    return (
        artifact(pins.skill),
        artifact(pins.playbook),
        artifact(pins.prompt),
        tuple(
            (item.tool_name, str(item.version))
            for item in pins.tool_behaviors
        ),
        artifact(pins.model_adapter),
        artifact(pins.state_contract),
    )


def _fingerprint(domain: str, value: JsonObject) -> str:
    encoded = json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(domain.encode("utf-8") + b"\0" + encoded).hexdigest()


def _json_identity_fingerprint(value: JsonValue) -> str:
    encoded = json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(b"study-agent-capability-json-identity-v1\0" + encoded).hexdigest()


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value
