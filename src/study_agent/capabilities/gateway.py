"""Authority-bound lifecycle gateway over trusted playbook checkpoints."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import NoReturn

from study_agent.domain import CourseId, ExecutionContext, PrincipalKind, RunId, SessionId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
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
    TutorCapabilityId,
)
from .registry import StudyCapabilityRegistry


@dataclass(frozen=True, slots=True)
class _RequestSlotReceipt:
    manifest_identity: str
    manifest_fingerprint: str
    authority_fingerprint: str
    request_authority_fingerprint: str
    input_fingerprint: str
    definition_fingerprint: str
    pins: tuple[JsonValue, ...]


class StudyCapabilityGateway:
    """Execute only the capability explicitly selected by a trusted host."""

    def __init__(
        self,
        *,
        bindings: tuple[CapabilityBinding, ...],
        engine: PlaybookEngine,
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
        self._request_slots: dict[str, _RequestSlotReceipt] = {}

    def discover(self) -> tuple[CapabilityManifest, ...]:
        return self._registry.discover()

    async def start(
        self,
        capability_or_request: CapabilityIdentifier | CapabilityRequest,
        inputs_or_context: JsonObject | ExecutionContext,
        context: ExecutionContext | None = None,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        if isinstance(capability_or_request, CapabilityRequest):
            if not isinstance(inputs_or_context, ExecutionContext) or context is not None:
                raise TypeError("CapabilityRequest start requires one execution context")
            return await self._start_request(
                capability_or_request,
                inputs_or_context,
                cancellation=cancellation,
            )
        if not isinstance(inputs_or_context, Mapping) or context is None:
            raise TypeError("capability start requires inputs and execution context")
        binding = self._binding(capability_or_request)
        return await self._start_bound(
            binding,
            inputs_or_context,
            inputs_or_context,
            context,
            cancellation=cancellation,
        )

    async def start_request(
        self,
        request: CapabilityRequest,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        """Execute a canonical request through its exact manifest identity."""

        return await self.start(request, context, cancellation=cancellation)

    async def _start_request(
        self,
        request: CapabilityRequest,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None,
    ) -> CapabilityOutcome:
        binding = self._binding_identity(request.manifest_identity)
        authority, _legacy_retry = self._authorize(binding, context)
        self._validate_request_authority(request, binding, context)
        public_inputs = request.inputs
        try:
            validate_json(public_inputs, binding.manifest.input_schema)
        except (SchemaValidationError, ValueError, TypeError) as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INVALID_REQUEST,
                "capability inputs violate the manifest schema",
            ) from error
        run_id = _request_run_id(request.idempotency_key)
        slot = _request_slot_receipt(request, binding, authority)
        request_receipt = _request_receipt_dependency(
            request, binding, authority, public_inputs
        )
        previous_slot = self._request_slots.get(request.idempotency_key)
        if previous_slot is not None and previous_slot != slot:
            self._conflict("idempotency key was reused with changed request authority or input")
        inspected = self._inspect_request_optional(binding, run_id)
        if inspected is not None:
            self._require_start_retry(
                binding, inspected, public_inputs, request_receipt=request_receipt
            )
            return self._observed(
                binding,
                inspected,
                authority,
                request.retry_identity_fingerprint,
            )

        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                run_id, "capability execution was cancelled before commit"
            )
        dependencies = _dependencies(binding, context, public_inputs)
        dependencies = _with_request_receipt(dependencies, request_receipt)
        stale = _high_water_stale(request.expected_stream_high_water, dependencies, run_id)
        if stale is not None:
            return stale
        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                run_id, "capability execution was cancelled before commit"
            )
        self._request_slots[request.idempotency_key] = slot
        try:
            await self._engine.execute(
                run_id=run_id,
                skill=binding.skill,
                definition=binding.playbook,
                inputs=public_inputs,
                pins=binding.pins,
                read_dependencies=dependencies,
            )
        except PlaybookEngineError as error:
            if error.failure.code is EngineErrorCode.DUPLICATE_RUN:
                inspected = self._inspect_request_required(binding, run_id)
                self._require_start_retry(
                    binding, inspected, public_inputs, request_receipt=request_receipt
                )
                return self._observed(
                    binding,
                    inspected,
                    authority,
                    request.retry_identity_fingerprint,
                )
            return self._engine_error(run_id, error)
        inspected = self._inspect_request_required(binding, run_id)
        # Once the engine has persisted a checkpoint, the persisted observation
        # wins a host-cancellation race. A cancellation request cannot roll it
        # back or turn it into a second terminal result.
        return self._observed(
            binding,
            inspected,
            authority,
            request.retry_identity_fingerprint,
        )

    async def _start_bound(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        public_inputs: JsonObject,
        execution_inputs: JsonObject,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None = None,
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
            self._require_start_retry(binding, inspected, frozen_inputs)
            return self._observed(binding, inspected, authority, retry)

        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                run_id, "capability execution was cancelled before commit"
            )

        dependencies = _dependencies(binding, context, frozen_public_inputs)
        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                run_id, "capability execution was cancelled before commit"
            )
        try:
            await self._engine.execute(
                run_id=run_id,
                skill=binding.skill,
                definition=binding.playbook,
                inputs=frozen_inputs,
                pins=binding.pins,
                read_dependencies=dependencies,
            )
        except PlaybookEngineError as error:
            if error.failure.code is EngineErrorCode.DUPLICATE_RUN:
                inspected = self._inspect_required(binding, run_id)
                self._require_start_retry(binding, inspected, frozen_inputs)
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
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        if not isinstance(continuation, CapabilityContinuation):
            raise TypeError("continuation must be CapabilityContinuation")
        binding = self._binding(continuation.capability_id)
        return await self._resume_bound(
            binding, continuation, response, context, cancellation=cancellation
        )

    async def _resume_bound(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
        *,
        cancellation: Callable[[], bool] | None = None,
    ) -> CapabilityOutcome:
        authority, retry = self._authorize(binding, context)
        request_mode, continuation_retry = self._require_continuation_authority(
            binding, continuation, authority, retry, context
        )
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
            return self._observed(binding, inspected, authority, continuation_retry)

        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                continuation.run_id, "capability execution was cancelled before commit"
            )

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
        )
        if request_mode:
            dependencies = _with_request_receipt(
                dependencies,
                _persisted_request_receipt(continuation),
            )
        if _cancel_requested(cancellation):
            return CancelledCapabilityOutcome(
                continuation.run_id, "capability execution was cancelled before commit"
            )
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
                return self._observed(binding, raced, authority, continuation_retry)
            return self._engine_error(continuation.run_id, error)
        inspected = self._inspect_required(binding, continuation.run_id)
        self._require_persisted_resume(binding, continuation, inspected, frozen_response)
        return self._observed(binding, inspected, authority, continuation_retry)

    def _binding(self, capability_id: CapabilityIdentifier) -> CapabilityBinding:
        if not isinstance(capability_id, (TutorCapabilityId, str)):
            raise TypeError("capability id must use TutorCapabilityId")
        try:
            binding = self._bindings[capability_id]
        except KeyError as error:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "capability is not registered",
            ) from error
        if not isinstance(binding, CapabilityBinding):  # pragma: no cover - constructor guard
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
                "capability binding is not trusted",
            )
        return binding

    def _binding_identity(self, identity: str) -> CapabilityBinding:
        for binding in self._bindings.values():
            if binding.manifest.identity == identity:
                return binding
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.NOT_FOUND,
            "capability manifest identity is not registered",
        )

    def _validate_request_authority(
        self,
        request: CapabilityRequest,
        binding: CapabilityBinding,
        context: ExecutionContext,
    ) -> None:
        authority = request.authority
        if authority.principal_kind not in {PrincipalKind.HUMAN, PrincipalKind.SERVICE}:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "capability authority must be a trusted human or service",
            )
        request_grants = frozenset(grant.name for grant in authority.grants)
        if not set(binding.manifest.required_authority) <= request_grants:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "required capability authority was not granted",
            )
        context_session = None if context.session_id is None else str(context.session_id)
        if (
            authority.principal_kind is not context.principal_kind
            or authority.principal_id != context.principal_id
            or authority.correlation_id != str(context.correlation_id)
            or authority.session_id != context_session
            or request_grants != context.requested_capabilities
        ):
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.UNAUTHORIZED,
                "capability request authority does not match the host context",
            )

    def _inspect_request_optional(
        self,
        binding: CapabilityBinding,
        run_id: RunId,
    ) -> InspectedRunRecord | None:
        try:
            return self._inspect_optional(binding, run_id)
        except CapabilityGatewayError as error:
            if error.code is CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME:
                self._conflict("idempotency key already names another capability run")
            raise

    def _inspect_request_required(
        self,
        binding: CapabilityBinding,
        run_id: RunId,
    ) -> InspectedRunRecord:
        inspected = self._inspect_request_optional(binding, run_id)
        if inspected is None:
            raise CapabilityGatewayError(
                CapabilityGatewayErrorCode.NOT_FOUND,
                "capability checkpoint was not found",
            )
        return inspected

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
        *,
        request_receipt: ReadDependency | None = None,
    ) -> None:
        if inspected.definition_fingerprint != playbook_definition_fingerprint(
            binding.playbook
        ):
            self._conflict("persisted capability definition differs from trusted binding")
        if _json_identity_fingerprint(inspected.inputs) != _json_identity_fingerprint(inputs):
            self._conflict("idempotency identity was reused with different inputs")
        if _pins_payload(inspected.pins) != _pins_payload(binding.pins):
            self._conflict("persisted capability pins differ from the trusted binding")
        if request_receipt is not None:
            persisted_receipts = tuple(
                item
                for item in inspected.read_dependencies
                if item.kind == request_receipt.kind and item.id == request_receipt.id
            )
            if persisted_receipts != (request_receipt,):
                self._conflict("idempotency identity was reused with changed request metadata")

    def _require_continuation_authority(
        self,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        continuation: CapabilityContinuation,
        authority: str,
        retry: str,
        context: ExecutionContext,
    ) -> tuple[bool, str]:
        expected_run = _run_id(binding, authority, retry)
        request_mode = continuation.run_id == _request_run_id(context.idempotency_key or "")
        continuation_retry = retry
        if request_mode:
            public_inputs = _public_input_projection(binding, continuation.inputs)
            continuation_retry = _request_retry_identity(
                binding, context.idempotency_key or "", public_inputs
            )
            expected_run = _request_run_id(context.idempotency_key or "")
        if (
            continuation.capability_id != binding.manifest.id
            or continuation.run_id != expected_run
            or continuation.capability_version != binding.manifest.version
            or continuation.manifest_fingerprint != binding.manifest_fingerprint
            or continuation.authority_fingerprint != authority
            or continuation.retry_identity_fingerprint != continuation_retry
        ):
            self._conflict("continuation authority or capability binding changed")
        return request_mode, continuation_retry

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
            return FailedCapabilityOutcome(
                inspected.run_id, "capability terminated without a public result"
            )
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

    @staticmethod
    def _conflict(message: str) -> NoReturn:
        raise CapabilityGatewayError(CapabilityGatewayErrorCode.CONFLICT, message)


def _dependencies(
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    context: ExecutionContext,
    inputs: JsonObject,
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
    keys = tuple((item.kind, item.id) for item in dependencies)
    if len(set(keys)) != len(keys):
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependency resolver returned duplicate identities",
        )
    return dependencies


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
    digest = _fingerprint(
        "study-agent-capability-run-v1",
        {
            "capability_identity": binding.manifest.identity,
            "manifest_fingerprint": binding.manifest_fingerprint,
            "authority_fingerprint": authority,
            "retry_identity_fingerprint": retry,
        },
    )
    return RunId(f"capability-run-sha256:{digest}")


def _request_run_id(idempotency_key: str) -> RunId:
    """Return the durable retry slot without embedding mutable request facts."""

    digest = _fingerprint(
        "study-agent-capability-idempotency-slot-v1",
        {"idempotency_key": idempotency_key},
    )
    return RunId(f"capability-slot-sha256:{digest}")


def _request_retry_identity(
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    idempotency_key: str,
    inputs: JsonObject,
) -> str:
    input_fingerprint = _fingerprint(
        "study-agent-capability-request-input-v1",
        {"manifest_identity": binding.manifest.identity, "inputs": inputs},
    )
    return _fingerprint(
        "study-agent-capability-request-retry-v1",
        {"idempotency_key": idempotency_key, "input_fingerprint": input_fingerprint},
    )


def _request_slot_receipt(
    request: CapabilityRequest,
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    authority: str,
) -> _RequestSlotReceipt:
    return _RequestSlotReceipt(
        binding.manifest.identity,
        binding.manifest_fingerprint,
        authority,
        request.authority_fingerprint,
        request.input_fingerprint,
        playbook_definition_fingerprint(binding.playbook),
        _pins_payload(binding.pins),
    )


def _request_receipt_dependency(
    request: CapabilityRequest,
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    authority: str,
    inputs: JsonObject,
) -> ReadDependency:
    digest = _fingerprint(
        "study-agent-capability-idempotency-receipt-v1",
        {
            "idempotency_key": request.idempotency_key,
            "manifest_identity": binding.manifest.identity,
            "manifest_fingerprint": binding.manifest_fingerprint,
            "authority_fingerprint": authority,
            "request_authority_fingerprint": request.authority_fingerprint,
            "input_fingerprint": request.input_fingerprint,
            "definition_fingerprint": playbook_definition_fingerprint(binding.playbook),
            "pins": _pins_payload(binding.pins),
            "inputs": inputs,
        },
    )
    return ReadDependency("capability.idempotency", request.idempotency_key, digest)


def _persisted_request_receipt(
    continuation: CapabilityContinuation,
) -> ReadDependency:
    receipts = tuple(
        item
        for item in continuation.read_dependencies
        if item.kind == "capability.idempotency"
    )
    if len(receipts) != 1:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.CONFLICT,
            "request continuation has no unique idempotency receipt",
        )
    return receipts[0]


def _with_request_receipt(
    dependencies: tuple[ReadDependency, ...], receipt: ReadDependency
) -> tuple[ReadDependency, ...]:
    if any(item.kind == receipt.kind and item.id == receipt.id for item in dependencies):
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability dependency resolver used a reserved idempotency identity",
        )
    return (*dependencies, receipt)


def _high_water_stale(
    expected: int,
    dependencies: tuple[ReadDependency, ...],
    run_id: RunId,
) -> StaleCapabilityOutcome | None:
    """Reject a request whose declared stream high-water is not in its read set.

    Capability dependency resolvers encode stream observations as
    ``sequence-N`` versions. A request with no sequence observation is only
    valid at the empty-stream high-water (zero); this keeps a request from
    silently executing against an unbound stream.
    """

    observed: list[int] = []
    for dependency in dependencies:
        if not dependency.version.startswith("sequence-"):
            continue
        value = dependency.version.removeprefix("sequence-")
        if not value.isdigit():
            return StaleCapabilityOutcome(
                run_id, "capability read dependency has an invalid stream high-water"
            )
        observed.append(int(value))
    if not observed:
        if expected == 0:
            return None
        return StaleCapabilityOutcome(
            run_id, "capability request stream high-water could not be verified"
        )
    if len(set(observed)) != 1 or observed[0] != expected:
        return StaleCapabilityOutcome(
            run_id, "capability request stream high-water is stale"
        )
    return None


def _cancel_requested(cancellation: Callable[[], bool] | None) -> bool:
    if cancellation is None:
        return False
    try:
        requested = cancellation()
    except Exception as error:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
            "capability cancellation probe failed safely",
        ) from error
    if type(requested) is not bool:
        raise CapabilityGatewayError(
            CapabilityGatewayErrorCode.INVALID_REQUEST,
            "capability cancellation probe must return a boolean",
        )
    return requested


def _pins_payload(pins: VersionPins) -> tuple[JsonValue, ...]:
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
