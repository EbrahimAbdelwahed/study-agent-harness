"""Gateway-backed adapter for isolated generation workers."""

from __future__ import annotations

from collections.abc import Mapping

from study_agent.domain import ExecutionContext, RunId
from study_agent.domain._validation import JsonValue
from study_agent.playbooks import (
    ModelStep,
    PlaybookRunStatus,
    StepTraceStatus,
    ToolStep,
    ValidateStep,
    ValidatorDisposition,
    VerifiedRunRecord,
    playbook_definition_fingerprint,
)
from study_agent.workers.contracts import (
    ChildCapabilityObservation,
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    ObservedValidationReceipt,
    ValidationReceiptSource,
    VerifiedPromptReceipt,
    fingerprint_output,
    fingerprint_run,
    fingerprint_validations,
)
from study_agent.workers.proof import (
    TechnicalModelReceipt,
    VerifiedChildExecutionProof,
    VerifiedChildProofOwner,
    VerifiedToolOutput,
    verified_child_value_fingerprint,
)

from .bindings import CapabilityBinding, ProfiledCapabilityBinding
from .contracts import (
    CancelledCapabilityOutcome,
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CapabilityOutcome,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    SuspendedCapabilityOutcome,
    TerminatedCapabilityOutcome,
)
from .gateway import StudyCapabilityGateway


class GatewayIsolatedCapabilityRunAdapter:
    """Drive one trusted capability binding and preserve its sanitized proof."""

    def __init__(
        self,
        *,
        gateway: StudyCapabilityGateway,
        bindings: tuple[CapabilityBinding | ProfiledCapabilityBinding, ...],
        proof_owner: VerifiedChildProofOwner,
    ) -> None:
        if not isinstance(gateway, StudyCapabilityGateway):
            raise TypeError("worker adapter gateway must be StudyCapabilityGateway")
        values = tuple(bindings)
        if not values or not all(
            isinstance(item, (CapabilityBinding, ProfiledCapabilityBinding))
            for item in values
        ):
            raise ValueError("worker adapter requires trusted capability bindings")
        identities = tuple(
            (
                item.manifest.id,
                item.manifest.version,
                item.manifest_fingerprint,
                playbook_definition_fingerprint(item.playbook),
            )
            for item in values
        )
        if len(set(identities)) != len(values):
            raise ValueError("worker adapter bindings must be pairwise unique")
        if not isinstance(proof_owner, VerifiedChildProofOwner):
            raise TypeError("worker adapter proof owner is invalid")
        self._gateway = gateway
        self._bindings = values
        self._proof_owner = proof_owner

    async def start(
        self, task: GenerationWorkerTask, context: ExecutionContext
    ) -> ChildCapabilityObservation:
        binding = self._binding(task)
        try:
            outcome = await self._gateway._start_bound(
                binding,
                task.capability_inputs(),
                task.capability_inputs(),
                context,
            )
        except CapabilityGatewayError as error:
            return self._gateway_failure(task, None, error)
        return self._observe(task, binding, outcome, context)

    async def resume(
        self,
        task: GenerationWorkerTask,
        continuation: CapabilityContinuation,
        response: JsonValue,
        context: ExecutionContext,
    ) -> ChildCapabilityObservation:
        binding = self._binding(task)
        self._require_continuation(task, continuation)
        try:
            outcome = await self._gateway._resume_bound(
                binding, continuation, response, context
            )
        except CapabilityGatewayError as error:
            return self._gateway_failure(task, continuation.run_id, error)
        return self._observe(task, binding, outcome, context)

    def _binding(
        self, task: GenerationWorkerTask
    ) -> CapabilityBinding | ProfiledCapabilityBinding:
        if not isinstance(task, GenerationWorkerTask):
            raise TypeError("worker task must be GenerationWorkerTask")
        matches = tuple(
            item
            for item in self._bindings
            if item.manifest.id is task.capability_id
            and item.manifest.version == task.capability_version
            and item.manifest_fingerprint == task.manifest_fingerprint
            and item.pins == task.pins
            and playbook_definition_fingerprint(item.playbook)
            == task.definition_fingerprint
            and item.manifest.output_schema == task.output_schema
            and item.manifest.required_authority == task.required_authority
        )
        if len(matches) != 1:
            raise ValueError("worker task does not select one exact trusted binding")
        return matches[0]

    @staticmethod
    def _require_continuation(
        task: GenerationWorkerTask, continuation: CapabilityContinuation
    ) -> None:
        if not isinstance(continuation, CapabilityContinuation):
            raise TypeError("worker continuation is invalid")
        if (
            continuation.capability_id is not task.capability_id
            or continuation.capability_version != task.capability_version
            or continuation.manifest_fingerprint != task.manifest_fingerprint
            or continuation.definition_fingerprint != task.definition_fingerprint
            or continuation.pins != task.pins
            or continuation.inputs != task.capability_inputs()
        ):
            raise ValueError("worker task and continuation bindings differ")

    def _observe(
        self,
        task: GenerationWorkerTask,
        binding: CapabilityBinding | ProfiledCapabilityBinding,
        outcome: CapabilityOutcome,
        context: ExecutionContext,
    ) -> ChildCapabilityObservation:
        if isinstance(outcome, SuspendedCapabilityOutcome):
            return _base(
                task,
                GenerationWorkerStatus.SUSPENDED,
                outcome.run_id,
                continuation=outcome.continuation,
            )
        if isinstance(outcome, CancelledCapabilityOutcome):
            return _base(
                task,
                GenerationWorkerStatus.CANCELLED,
                outcome.run_id,
                failure_code="gateway_cancelled",
            )
        if isinstance(outcome, StaleCapabilityOutcome):
            return _base(
                task,
                GenerationWorkerStatus.STALE,
                outcome.run_id,
                failure_code="gateway_stale",
            )
        if isinstance(outcome, FailedCapabilityOutcome):
            return _base(
                task,
                GenerationWorkerStatus.FAILED,
                outcome.run_id,
                failure_code="gateway_failed",
            )
        if isinstance(outcome, TerminatedCapabilityOutcome):
            return _base(
                task,
                GenerationWorkerStatus.TERMINATED,
                outcome.run.run_id,
                verified_run=outcome.run,
                failure_code="gateway_terminated",
            )
        if not isinstance(outcome, CompletedCapabilityOutcome):
            raise TypeError("gateway returned an unknown capability outcome")
        try:
            observation, _ = _completed_observation(task, binding, outcome)
            receipt = _expected_completed_receipt(task, observation)
            self._proof_owner.create(
                task,
                receipt,
                outcome.run,
                binding.playbook,
                outcome.output,
                context,
            )
            return observation
        except Exception:
            return _base(
                task,
                GenerationWorkerStatus.FAILED,
                outcome.run.run_id,
                failure_code="child_proof_invalid",
            )

    @staticmethod
    def _gateway_failure(
        task: GenerationWorkerTask,
        run_id: RunId | None,
        error: CapabilityGatewayError,
    ) -> ChildCapabilityObservation:
        selected = run_id or _failed_run_id(task)
        if error.code is CapabilityGatewayErrorCode.IN_PROGRESS and error.retryable:
            return _base(task, GenerationWorkerStatus.RUNNING, selected)
        return _base(
            task,
            GenerationWorkerStatus.FAILED,
            selected,
            failure_code=f"gateway_{error.code.value}",
        )


def _completed_observation(
    task: GenerationWorkerTask,
    binding: CapabilityBinding | ProfiledCapabilityBinding,
    outcome: CompletedCapabilityOutcome,
) -> tuple[ChildCapabilityObservation, VerifiedChildExecutionProof]:
    run = outcome.run
    if (
        run.status is not PlaybookRunStatus.COMPLETED
        or run.run_id != outcome.run.run_id
        or run.definition_fingerprint != task.definition_fingerprint
        or run.pins != task.pins
        or run.inputs != task.capability_inputs()
    ):
        raise ValueError("verified gateway run differs from worker task")
    steps = {step.id: step for step in binding.playbook.steps}
    tools: list[VerifiedToolOutput] = []
    validations: list[ObservedValidationReceipt] = []
    models: list[TechnicalModelReceipt] = []
    prompts: list[VerifiedPromptReceipt] = []
    for trace in run.traces:
        if trace.status is not StepTraceStatus.COMPLETED:
            continue
        step = steps.get(trace.step_id)
        if step is None or trace.step_kind != step.kind:
            raise ValueError("verified trace does not match bound playbook")
        if isinstance(step, ToolStep):
            value = run.outputs[step.output_key]
            tools.append(
                VerifiedToolOutput(
                    step.id,
                    step.output_key,
                    step.tool.id,
                    str(step.tool.version),
                    value,
                    verified_child_value_fingerprint(value),
                )
            )
        elif isinstance(step, ModelStep):
            models.append(_technical_model(trace.details))
            prompt = _prompt(trace.details)
            if prompt is not None:
                prompts.append(prompt)
            validations.extend(_fallback_validations(step.id, trace.details))
        elif isinstance(step, ValidateStep):
            validations.append(_validation(step, trace.details))
    if len(models) != 1 or len(prompts) != 1:
        raise ValueError("completed child requires one model and prompt receipt")
    observed = tuple(validations)
    expected = tuple(
        (item.step_id, item.source, item.validator_id, item.validator_version)
        for item in task.expected_validations
    )
    actual = tuple(
        (item.step_id, item.source, item.validator_id, item.validator_version)
        for item in observed
    )
    if actual != expected or not all(
        item.passed and item.disposition is ValidatorDisposition.CONTINUE
        for item in observed
    ):
        raise ValueError("verified validation provenance differs from worker task")
    prompt = prompts[0]
    observation = ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        run.run_id,
        task.pins,
        task.definition_fingerprint,
        task.output_schema_fingerprint,
        observed,
        prompt,
        verified_run=run,
        output=outcome.output,
    )
    proof = VerifiedChildExecutionProof(
        run.run_id,
        GenerationWorkerStatus.COMPLETED,
        run.definition_fingerprint,
        run.pins,
        task.payload_fingerprint,
        outcome.output,
        fingerprint_output(outcome.output),
        run.read_dependencies,
        tuple(tools),
        models[0],
        prompt,
        observed,
    )
    return observation, proof


def _technical_model(details: Mapping[str, JsonValue]) -> TechnicalModelReceipt:
    invocation = _mapping(details.get("model_invocation"), "model invocation")
    if set(invocation) != {"adapter_id", "adapter_version", "model_id", "response_id"}:
        raise ValueError("model invocation fields are not exact")
    usage_value = details.get("model_usage")
    input_tokens: int | None = None
    output_tokens: int | None = None
    if usage_value is not None:
        usage = _mapping(usage_value, "model usage")
        if set(usage) != {"input_tokens", "output_tokens"}:
            raise ValueError("model usage fields are not exact")
        input_tokens = _integer(usage["input_tokens"], "input_tokens")
        output_tokens = _integer(usage["output_tokens"], "output_tokens")
    response = invocation["response_id"]
    if response is not None and not isinstance(response, str):
        raise ValueError("model response id must be text or null")
    return TechnicalModelReceipt(
        _string(invocation, "adapter_id"),
        _string(invocation, "adapter_version"),
        _string(invocation, "model_id"),
        response,
        input_tokens,
        output_tokens,
    )


def _prompt(details: Mapping[str, JsonValue]) -> VerifiedPromptReceipt | None:
    value = details.get("prompt")
    if value is None:
        return None
    prompt = _mapping(value, "prompt receipt")
    if set(prompt) != {"id", "version", "fingerprint", "layers"}:
        raise ValueError("prompt receipt fields are not exact")
    layers_value = prompt["layers"]
    if not isinstance(layers_value, tuple):
        raise ValueError("prompt layers must be an array")
    layers: list[str] = []
    for item in layers_value:
        layer = _mapping(item, "prompt layer")
        if set(layer) != {"id", "version", "kind", "input_fingerprint"}:
            raise ValueError("prompt layer fields are not exact")
        layers.append(_string(layer, "input_fingerprint"))
    return VerifiedPromptReceipt(
        _string(prompt, "id"),
        _string(prompt, "version"),
        _string(prompt, "fingerprint"),
        tuple(layers),
    )


def _fallback_validations(
    step_id: str, details: Mapping[str, JsonValue]
) -> tuple[ObservedValidationReceipt, ...]:
    value = details.get("fallback_validators", ())
    if not isinstance(value, tuple):
        raise ValueError("fallback validator receipts must be an array")
    return tuple(
        _validation_receipt(
            step_id,
            ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
            _mapping(item, "fallback validation receipt"),
        )
        for item in value
    )


def _validation(
    step: ValidateStep, details: Mapping[str, JsonValue]
) -> ObservedValidationReceipt:
    receipt = _mapping(details.get("validator"), "validation receipt")
    observed = _validation_receipt(
        step.id, ValidationReceiptSource.VALIDATE_STEP, receipt
    )
    if (
        observed.validator_id != step.validator.id
        or observed.validator_version != str(step.validator.version)
    ):
        raise ValueError("validation receipt differs from declared step")
    return observed


def _validation_receipt(
    step_id: str,
    source: ValidationReceiptSource,
    receipt: Mapping[str, JsonValue],
) -> ObservedValidationReceipt:
    allowed = {
        "validator_id", "validator_version", "passed", "disposition",
        "result_fingerprint", "reason",
    }
    if set(receipt) not in (allowed, {*allowed, "result"}):
        raise ValueError("validation receipt fields are not exact")
    passed = receipt["passed"]
    if type(passed) is not bool:
        raise ValueError("validation passed must be boolean")
    return ObservedValidationReceipt(
        step_id,
        source,
        _string(receipt, "validator_id"),
        _string(receipt, "validator_version"),
        passed,
        _string(receipt, "result_fingerprint"),
        ValidatorDisposition(_string(receipt, "disposition")),
    )


def _expected_completed_receipt(
    task: GenerationWorkerTask, observation: ChildCapabilityObservation
) -> GenerationWorkerReceipt:
    assert observation.prompt is not None
    return GenerationWorkerReceipt(
        task.task_id,
        task.task_kind,
        GenerationWorkerStatus.COMPLETED,
        observation.run_id,
        task.fingerprint,
        task.pins_fingerprint,
        task.payload_fingerprint,
        fingerprint_output(observation.output),
        fingerprint_validations(observation.validations),
        fingerprint_run(observation),
        observation.prompt.composition_fingerprint,
    )


def _base(
    task: GenerationWorkerTask,
    status: GenerationWorkerStatus,
    run_id: RunId,
    *,
    continuation: CapabilityContinuation | None = None,
    verified_run: VerifiedRunRecord | None = None,
    failure_code: str | None = None,
) -> ChildCapabilityObservation:
    return ChildCapabilityObservation(
        status,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        run_id,
        task.pins,
        task.definition_fingerprint,
        task.output_schema_fingerprint,
        continuation=continuation,
        verified_run=verified_run,
        failure_code=failure_code,
    )


def _failed_run_id(task: GenerationWorkerTask) -> RunId:
    return RunId(f"worker-failed:{task.fingerprint}")


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be text")
    return item


def _integer(value: JsonValue, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
