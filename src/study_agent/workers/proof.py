"""Sanitized, atomic proof of one verified child capability execution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import cast

from study_agent.domain import ExecutionContext, RunId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.playbooks import (
    ModelStep,
    PlaybookDefinition,
    PlaybookRunStatus,
    ReadDependency,
    StepTraceStatus,
    ToolStep,
    ValidateStep,
    ValidatorDisposition,
    VerifiedRunRecord,
    VersionPins,
    playbook_definition_fingerprint,
)
from study_agent.ports.worker import VerifiedChildProofStore
from study_agent.state import canonical_json_bytes

from .contracts import (
    MAX_STORED_STATE_BYTES,
    ChildCapabilityObservation,
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    ObservedValidationReceipt,
    ValidationReceiptSource,
    VerifiedPromptReceipt,
    fingerprint_execution_inputs,
    fingerprint_output,
    fingerprint_run,
    fingerprint_validations,
    pins_from_json,
    pins_to_json,
)
from .service import GenerationWorkerConflictError, generation_worker_authority_fingerprint

_PROOF_DOMAIN = "verified-child-execution-proof@1"
_SLOT_DOMAIN = "verified-child-proof-slot@1"


@dataclass(frozen=True, slots=True)
class VerifiedToolOutput:
    step_id: str
    output_key: str
    tool_id: str
    tool_version: str
    value: JsonValue
    fingerprint: str

    def __post_init__(self) -> None:
        for item, name in (
            (self.step_id, "tool step id"),
            (self.output_key, "tool output key"),
            (self.tool_id, "tool id"),
            (self.tool_version, "tool version"),
        ):
            _text(item, name)
        value = freeze_json(self.value)
        object.__setattr__(self, "value", value)
        if self.fingerprint != _json_fingerprint(value):
            raise ValueError("tool output fingerprint does not match value")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "step_id": self.step_id,
                "output_key": self.output_key,
                "tool_id": self.tool_id,
                "tool_version": self.tool_version,
                "value": self.value,
                "fingerprint": self.fingerprint,
            }
        )


@dataclass(frozen=True, slots=True)
class TechnicalModelReceipt:
    adapter_id: str
    adapter_version: str
    model_id: str
    response_id: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for item, name in (
            (self.adapter_id, "adapter id"),
            (self.adapter_version, "adapter version"),
            (self.model_id, "model id"),
        ):
            _text(item, name)
        if self.response_id is not None:
            _text(self.response_id, "response id")
        if (self.input_tokens is None) != (self.output_tokens is None):
            raise ValueError("model token usage must be complete or absent")
        for token_count in (self.input_tokens, self.output_tokens):
            if token_count is not None and (
                type(token_count) is not int or token_count < 0
            ):
                raise ValueError("model token usage must be non-negative integers")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "adapter_id": self.adapter_id,
                "adapter_version": self.adapter_version,
                "model_id": self.model_id,
                "response_id": self.response_id,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            }
        )


@dataclass(frozen=True, slots=True)
class VerifiedChildExecutionProof:
    run_id: RunId
    status: GenerationWorkerStatus
    definition_fingerprint: str
    pins: VersionPins
    input_fingerprint: str
    output: JsonValue
    output_fingerprint: str
    read_dependencies: tuple[ReadDependency, ...]
    tool_outputs: tuple[VerifiedToolOutput, ...]
    model: TechnicalModelReceipt
    prompt: VerifiedPromptReceipt
    validations: tuple[ObservedValidationReceipt, ...]
    execution_input_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, RunId):
            raise TypeError("proof run_id must be RunId")
        if self.status is not GenerationWorkerStatus.COMPLETED:
            raise ValueError("verified child proofs require completed status")
        _sha(self.definition_fingerprint, "definition fingerprint")
        if not isinstance(self.pins, VersionPins):
            raise TypeError("proof pins must use VersionPins")
        _sha(self.input_fingerprint, "input fingerprint")
        execution_fingerprint = self.execution_input_fingerprint or self.input_fingerprint
        _sha(execution_fingerprint, "execution input fingerprint")
        object.__setattr__(self, "execution_input_fingerprint", execution_fingerprint)
        output = freeze_json(self.output)
        object.__setattr__(self, "output", output)
        if self.output_fingerprint != fingerprint_output(output):
            raise ValueError("proof output fingerprint does not match output")
        dependencies = tuple(self.read_dependencies)
        if not all(isinstance(item, ReadDependency) for item in dependencies):
            raise TypeError("proof dependencies must use ReadDependency")
        if len({(item.kind, item.id) for item in dependencies}) != len(dependencies):
            raise ValueError("proof dependencies must be unique by kind and id")
        object.__setattr__(self, "read_dependencies", dependencies)
        tools = tuple(self.tool_outputs)
        if not all(isinstance(item, VerifiedToolOutput) for item in tools):
            raise TypeError("proof tool outputs are invalid")
        if len({item.step_id for item in tools}) != len(tools):
            raise ValueError("proof tool outputs must be unique by step")
        object.__setattr__(self, "tool_outputs", tools)
        if not isinstance(self.model, TechnicalModelReceipt):
            raise TypeError("proof model receipt is invalid")
        if not isinstance(self.prompt, VerifiedPromptReceipt):
            raise TypeError("proof prompt receipt is invalid")
        validations = tuple(self.validations)
        if not validations or not all(
            isinstance(item, ObservedValidationReceipt) for item in validations
        ):
            raise ValueError("proof validations must be non-empty receipts")
        object.__setattr__(self, "validations", validations)
        if len(self.to_bytes()) > MAX_STORED_STATE_BYTES:
            raise ValueError("verified child proof exceeds 512 KiB")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_PROOF_DOMAIN, self.to_json())

    def to_json(self) -> JsonObject:
        value: dict[str, JsonValue] = {
                "run_id": str(self.run_id),
                "status": self.status.value,
                "definition_fingerprint": self.definition_fingerprint,
                "pins": pins_to_json(self.pins),
                "input_fingerprint": self.input_fingerprint,
                "output": self.output,
                "output_fingerprint": self.output_fingerprint,
                "read_dependencies": tuple(
                    {"kind": item.kind, "id": item.id, "version": item.version}
                    for item in self.read_dependencies
                ),
                "tool_outputs": tuple(item.to_json() for item in self.tool_outputs),
                "model": self.model.to_json(),
                "prompt": self.prompt.to_json(),
                "validations": tuple(item.to_json() for item in self.validations),
            }
        if self.execution_input_fingerprint != self.input_fingerprint:
            value["execution_input_fingerprint"] = self.execution_input_fingerprint
        return freeze_object(value)

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> VerifiedChildExecutionProof:
        if len(data) > MAX_STORED_STATE_BYTES:
            raise ValueError("verified child proof exceeds 512 KiB")
        value = _object(data, "verified child proof")
        base_fields = {
                "run_id", "status", "definition_fingerprint", "pins",
                "input_fingerprint", "output", "output_fingerprint",
                "read_dependencies", "tool_outputs", "model", "prompt", "validations",
            }
        if set(value) not in (base_fields, {*base_fields, "execution_input_fingerprint"}):
            raise ValueError("verified child proof fields are not exact")
        execution_fingerprint = value.get(
            "execution_input_fingerprint", value["input_fingerprint"]
        )
        if not isinstance(execution_fingerprint, str):
            raise ValueError("execution input fingerprint must be text")
        proof = cls(
            RunId(_string(value, "run_id")),
            GenerationWorkerStatus(_string(value, "status")),
            _string(value, "definition_fingerprint"),
            pins_from_json(_mapping(value, "pins")),
            _string(value, "input_fingerprint"),
            value["output"],
            _string(value, "output_fingerprint"),
            tuple(_dependency(item) for item in _array(value, "read_dependencies")),
            tuple(_tool(item) for item in _array(value, "tool_outputs")),
            _model(_mapping(value, "model")),
            _prompt(_mapping(value, "prompt")),
            tuple(_validation(item) for item in _array(value, "validations")),
            execution_fingerprint,
        )
        if proof.to_bytes() != data:
            raise ValueError("verified child proof bytes are not canonical")
        return proof


VerifiedChildExecutionProofView = VerifiedChildExecutionProof


@dataclass(frozen=True, slots=True)
class _ProofSlot:
    task_fingerprint: str
    authority_fingerprint: str
    receipt_fingerprint: str
    proof: VerifiedChildExecutionProof

    def __post_init__(self) -> None:
        _sha(self.task_fingerprint, "task fingerprint")
        _sha(self.authority_fingerprint, "authority fingerprint")
        _sha(self.receipt_fingerprint, "receipt fingerprint")

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "task_fingerprint": self.task_fingerprint,
                "authority_fingerprint": self.authority_fingerprint,
                "receipt_fingerprint": self.receipt_fingerprint,
                "proof": self.proof.to_json(),
                "slot_fingerprint": _fingerprint(
                    _SLOT_DOMAIN,
                    freeze_object(
                        {
                            "task_fingerprint": self.task_fingerprint,
                            "authority_fingerprint": self.authority_fingerprint,
                            "receipt_fingerprint": self.receipt_fingerprint,
                            "proof_fingerprint": self.proof.fingerprint,
                        }
                    ),
                ),
            }
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> _ProofSlot:
        if len(data) > MAX_STORED_STATE_BYTES:
            raise ValueError("verified child proof slot exceeds 512 KiB")
        value = _object(data, "verified child proof slot")
        _exact(
            value,
            {
                "task_fingerprint",
                "authority_fingerprint",
                "receipt_fingerprint",
                "proof",
                "slot_fingerprint",
            },
            "verified child proof slot",
        )
        proof = VerifiedChildExecutionProof.from_bytes(
            canonical_json_bytes(_mapping(value, "proof"))
        )
        slot = cls(
            _string(value, "task_fingerprint"),
            _string(value, "authority_fingerprint"),
            _string(value, "receipt_fingerprint"),
            proof,
        )
        expected = slot.to_json()["slot_fingerprint"]
        if value["slot_fingerprint"] != expected or slot.to_bytes() != data:
            raise ValueError("verified child proof slot is not canonical or was changed")
        return slot


class VerifiedChildProofOwner:
    """Own the sole durable proof slot for each child run."""

    def __init__(self, store: VerifiedChildProofStore) -> None:
        self._store = store

    def create(
        self,
        task: GenerationWorkerTask,
        receipt: GenerationWorkerReceipt,
        run: VerifiedRunRecord,
        definition: PlaybookDefinition,
        output: JsonValue,
        parent: ExecutionContext,
        execution_inputs: JsonObject | None = None,
    ) -> VerifiedChildExecutionProofView:
        exact_inputs = execution_inputs or task.capability_inputs()
        proof = _proof_from_run(task, run, definition, output, exact_inputs)
        _verify(task, receipt, proof)
        _verify_against_run(task, receipt, proof, run, definition, exact_inputs)
        slot = _ProofSlot(
            task.fingerprint,
            generation_worker_authority_fingerprint(task, parent),
            receipt.fingerprint,
            proof,
        )
        payload = slot.to_bytes()
        if len(payload) > MAX_STORED_STATE_BYTES:
            raise ValueError("verified child proof slot exceeds 512 KiB")
        key = proof.run_id
        if self._store.create(key, payload):
            return proof
        existing = _ProofSlot.from_bytes(self._store.load(key))
        if existing.to_bytes() != payload:
            raise GenerationWorkerConflictError("child run proof already has another owner")
        return existing.proof

    def load(
        self,
        task: GenerationWorkerTask,
        run_id: RunId,
        receipt: GenerationWorkerReceipt,
        parent: ExecutionContext,
        execution_inputs: JsonObject | None = None,
    ) -> VerifiedChildExecutionProofView:
        if receipt.status is not GenerationWorkerStatus.COMPLETED:
            raise GenerationWorkerConflictError("proof lookup requires completed receipt")
        slot = _ProofSlot.from_bytes(self._store.load(run_id))
        authority = generation_worker_authority_fingerprint(task, parent)
        if (
            slot.task_fingerprint != task.fingerprint
            or slot.authority_fingerprint != authority
            or slot.receipt_fingerprint != receipt.fingerprint
            or slot.proof.run_id != run_id
        ):
            raise GenerationWorkerConflictError("proof lookup identity changed")
        _verify(task, receipt, slot.proof)
        if slot.proof.execution_input_fingerprint != _execution_commitment(
            task, execution_inputs or task.capability_inputs()
        ):
            raise GenerationWorkerConflictError("proof execution inputs changed")
        return slot.proof


def _proof_from_run(
    task: GenerationWorkerTask,
    run: VerifiedRunRecord,
    definition: PlaybookDefinition,
    output: JsonValue,
    execution_inputs: JsonObject,
) -> VerifiedChildExecutionProof:
    if (
        run.status is not PlaybookRunStatus.COMPLETED
        or run.definition_fingerprint != task.definition_fingerprint
        or run.pins != task.pins
        or run.inputs != execution_inputs
        or playbook_definition_fingerprint(definition) != task.definition_fingerprint
    ):
        raise GenerationWorkerConflictError("engine run differs from worker task")
    tools, model, prompt, validations = _derive_run_provenance(run, definition)
    return VerifiedChildExecutionProof(
        run.run_id,
        GenerationWorkerStatus.COMPLETED,
        run.definition_fingerprint,
        run.pins,
        task.payload_fingerprint,
        output,
        fingerprint_output(output),
        run.read_dependencies,
        tools,
        model,
        prompt,
        validations,
        _execution_commitment(task, execution_inputs),
    )


def _execution_commitment(
    task: GenerationWorkerTask, execution_inputs: JsonObject
) -> str:
    if execution_inputs == task.capability_inputs():
        return task.payload_fingerprint
    return fingerprint_execution_inputs(execution_inputs)


def _verify(
    task: GenerationWorkerTask,
    receipt: GenerationWorkerReceipt,
    proof: VerifiedChildExecutionProof,
) -> None:
    expected_validations = tuple(
        (item.step_id, item.source, item.validator_id, item.validator_version)
        for item in task.expected_validations
    )
    actual_validations = tuple(
        (item.step_id, item.source, item.validator_id, item.validator_version)
        for item in proof.validations
    )
    synthetic_observation = ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        proof.run_id,
        proof.pins,
        proof.definition_fingerprint,
        task.output_schema_fingerprint,
        proof.validations,
        proof.prompt,
        verified_run=VerifiedRunRecord(
            proof.run_id,
            proof.definition_fingerprint,
            {},
            proof.pins,
            proof.read_dependencies,
            {},
            (),
            PlaybookRunStatus.COMPLETED,
        ),
        output=proof.output,
    )
    if (
        receipt.status is not GenerationWorkerStatus.COMPLETED
        or receipt.task_id != task.task_id
        or receipt.task_kind is not task.task_kind
        or receipt.task_fingerprint != task.fingerprint
        or receipt.child_run_id != proof.run_id
        or receipt.pins_fingerprint != task.pins_fingerprint
        or receipt.input_fingerprint != task.payload_fingerprint
        or proof.definition_fingerprint != task.definition_fingerprint
        or proof.pins != task.pins
        or proof.input_fingerprint != task.payload_fingerprint
        or proof.output_fingerprint != receipt.output_fingerprint
        or receipt.validator_fingerprint != fingerprint_validations(proof.validations)
        or receipt.run_fingerprint != fingerprint_run(synthetic_observation)
        or proof.prompt.composition_fingerprint != receipt.prompt_fingerprint
        or proof.prompt.prompt_id != task.pins.prompt.id
        or proof.prompt.prompt_version != str(task.pins.prompt.version)
        or proof.model.adapter_id != task.pins.model_adapter.id
        or proof.model.adapter_version != str(task.pins.model_adapter.version)
        or actual_validations != expected_validations
        or not all(
            item.passed and item.disposition is ValidatorDisposition.CONTINUE
            for item in proof.validations
        )
    ):
        raise GenerationWorkerConflictError("verified child proof commitments changed")


def _verify_against_run(
    task: GenerationWorkerTask,
    receipt: GenerationWorkerReceipt,
    proof: VerifiedChildExecutionProof,
    run: VerifiedRunRecord,
    definition: PlaybookDefinition,
    execution_inputs: JsonObject,
) -> None:
    if (
        not isinstance(run, VerifiedRunRecord)
        or run.status is not PlaybookRunStatus.COMPLETED
        or run.run_id != proof.run_id
        or run.definition_fingerprint != task.definition_fingerprint
        or run.inputs != execution_inputs
        or proof.execution_input_fingerprint != _execution_commitment(task, execution_inputs)
        or run.pins != task.pins
        or run.read_dependencies != proof.read_dependencies
        or definition.id != task.pins.playbook.id
        or definition.version != task.pins.playbook.version
    ):
        raise GenerationWorkerConflictError("verified engine run differs from proof owner")
    if not definition.steps:
        raise GenerationWorkerConflictError("verified definition has no output step")
    public_key = definition.steps[-1].output_key
    if run.outputs.get(public_key) != proof.output:
        raise GenerationWorkerConflictError("verified public output differs from engine run")

    tools, model, prompt, validations = _derive_run_provenance(run, definition)
    if (
        tools != proof.tool_outputs
        or model != proof.model
        or prompt != proof.prompt
        or validations != proof.validations
    ):
        raise GenerationWorkerConflictError("sanitized proof differs from engine receipts")
    observation = ChildCapabilityObservation(
        GenerationWorkerStatus.COMPLETED,
        task.capability_id,
        task.capability_version,
        task.manifest_fingerprint,
        run.run_id,
        run.pins,
        run.definition_fingerprint,
        task.output_schema_fingerprint,
        validations,
        prompt,
        verified_run=run,
        output=proof.output,
    )
    if fingerprint_run(observation) != receipt.run_fingerprint:
        raise GenerationWorkerConflictError("engine run fingerprint differs from receipt")


def _derive_run_provenance(
    run: VerifiedRunRecord, definition: PlaybookDefinition
) -> tuple[
    tuple[VerifiedToolOutput, ...],
    TechnicalModelReceipt,
    VerifiedPromptReceipt,
    tuple[ObservedValidationReceipt, ...],
]:
    steps = {step.id: step for step in definition.steps}
    tools: list[VerifiedToolOutput] = []
    models: list[TechnicalModelReceipt] = []
    prompts: list[VerifiedPromptReceipt] = []
    validations: list[ObservedValidationReceipt] = []
    for trace in run.traces:
        if trace.status is not StepTraceStatus.COMPLETED:
            continue
        step = steps.get(trace.step_id)
        if step is None or step.kind != trace.step_kind:
            raise GenerationWorkerConflictError("engine trace differs from definition")
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
            model, prompt, fallback = _model_trace_provenance(step.id, trace.details)
            models.append(model)
            if prompt is not None:
                prompts.append(prompt)
            validations.extend(fallback)
        elif isinstance(step, ValidateStep):
            raw = _as_mapping(trace.details.get("validator"), "validator receipt")
            validation = _observed_validation(
                step.id, ValidationReceiptSource.VALIDATE_STEP, raw
            )
            if (
                validation.validator_id != step.validator.id
                or validation.validator_version != str(step.validator.version)
            ):
                raise GenerationWorkerConflictError(
                    "validator receipt differs from definition"
                )
            validations.append(validation)
    if len(models) != 1 or len(prompts) != 1:
        raise GenerationWorkerConflictError(
            "verified run requires one model and prompt receipt"
        )
    return tuple(tools), models[0], prompts[0], tuple(validations)


def _model_trace_provenance(
    step_id: str, details: Mapping[str, JsonValue]
) -> tuple[
    TechnicalModelReceipt,
    VerifiedPromptReceipt | None,
    tuple[ObservedValidationReceipt, ...],
]:
    invocation = _as_mapping(details.get("model_invocation"), "model invocation")
    _exact(
        invocation,
        {"adapter_id", "adapter_version", "model_id", "response_id"},
        "model invocation",
    )
    response_id = invocation["response_id"]
    if response_id is not None and not isinstance(response_id, str):
        raise GenerationWorkerConflictError("model response id is invalid")
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_value = details.get("model_usage")
    if usage_value is not None:
        usage = _as_mapping(usage_value, "model usage")
        _exact(usage, {"input_tokens", "output_tokens"}, "model usage")
        input_tokens = _optional_int(usage["input_tokens"], "input_tokens")
        output_tokens = _optional_int(usage["output_tokens"], "output_tokens")
        if input_tokens is None or output_tokens is None:
            raise GenerationWorkerConflictError("model usage cannot contain null")
    model = TechnicalModelReceipt(
        _string(invocation, "adapter_id"),
        _string(invocation, "adapter_version"),
        _string(invocation, "model_id"),
        response_id,
        input_tokens,
        output_tokens,
    )
    prompt_value = details.get("prompt")
    prompt: VerifiedPromptReceipt | None = None
    if prompt_value is not None:
        raw_prompt = _as_mapping(prompt_value, "prompt receipt")
        _exact(
            raw_prompt,
            {"id", "version", "fingerprint", "layers"},
            "prompt receipt",
        )
        layers = raw_prompt["layers"]
        if not isinstance(layers, tuple):
            raise GenerationWorkerConflictError("prompt layers are invalid")
        fingerprints: list[str] = []
        for value in layers:
            layer = _as_mapping(value, "prompt layer")
            _exact(
                layer,
                {"id", "version", "kind", "input_fingerprint"},
                "prompt layer",
            )
            fingerprints.append(_string(layer, "input_fingerprint"))
        prompt = VerifiedPromptReceipt(
            _string(raw_prompt, "id"),
            _string(raw_prompt, "version"),
            _string(raw_prompt, "fingerprint"),
            tuple(fingerprints),
        )
    raw_fallbacks = details.get("fallback_validators", ())
    if not isinstance(raw_fallbacks, tuple):
        raise GenerationWorkerConflictError("fallback validator receipts are invalid")
    fallbacks = tuple(
        _observed_validation(
            step_id,
            ValidationReceiptSource.STRUCTURED_OUTPUT_FALLBACK,
            _as_mapping(value, "fallback validator receipt"),
        )
        for value in raw_fallbacks
    )
    return model, prompt, fallbacks


def _observed_validation(
    step_id: str,
    source: ValidationReceiptSource,
    value: Mapping[str, JsonValue],
) -> ObservedValidationReceipt:
    expected = {
        "validator_id",
        "validator_version",
        "passed",
        "disposition",
        "result_fingerprint",
        "reason",
    }
    embedded = {"step_id", "source"}
    if set(value) not in (
        expected,
        {*expected, "result"},
        {*expected, *embedded},
        {*expected, *embedded, "result"},
    ):
        raise GenerationWorkerConflictError("validator receipt fields are invalid")
    if embedded <= set(value) and (
        value["step_id"] != step_id or value["source"] != source.value
    ):
        raise GenerationWorkerConflictError(
            "embedded validator receipt identity differs from trace"
        )
    passed = value["passed"]
    if type(passed) is not bool:
        raise GenerationWorkerConflictError("validator passed value is invalid")
    return ObservedValidationReceipt(
        step_id,
        source,
        _string(value, "validator_id"),
        _string(value, "validator_version"),
        passed,
        _string(value, "result_fingerprint"),
        ValidatorDisposition(_string(value, "disposition")),
    )


def _dependency(value: JsonValue) -> ReadDependency:
    raw = _as_mapping(value, "read dependency")
    _exact(raw, {"kind", "id", "version"}, "read dependency")
    return ReadDependency(_string(raw, "kind"), _string(raw, "id"), _string(raw, "version"))


def _tool(value: JsonValue) -> VerifiedToolOutput:
    raw = _as_mapping(value, "tool output")
    _exact(
        raw,
        {"step_id", "output_key", "tool_id", "tool_version", "value", "fingerprint"},
        "tool output",
    )
    return VerifiedToolOutput(
        _string(raw, "step_id"), _string(raw, "output_key"),
        _string(raw, "tool_id"), _string(raw, "tool_version"),
        raw["value"], _string(raw, "fingerprint"),
    )


def _model(value: Mapping[str, JsonValue]) -> TechnicalModelReceipt:
    _exact(
        value,
        {
            "adapter_id",
            "adapter_version",
            "model_id",
            "response_id",
            "input_tokens",
            "output_tokens",
        },
        "model receipt",
    )
    response_id = value["response_id"]
    if response_id is not None and not isinstance(response_id, str):
        raise ValueError("model response_id must be text or null")
    return TechnicalModelReceipt(
        _string(value, "adapter_id"), _string(value, "adapter_version"),
        _string(value, "model_id"), response_id if isinstance(response_id, str) else None,
        _optional_int(value["input_tokens"], "input_tokens"),
        _optional_int(value["output_tokens"], "output_tokens"),
    )


def _prompt(value: Mapping[str, JsonValue]) -> VerifiedPromptReceipt:
    _exact(
        value,
        {"prompt_id", "prompt_version", "composition_fingerprint", "layer_fingerprints"},
        "prompt receipt",
    )
    return VerifiedPromptReceipt(
        _string(value, "prompt_id"), _string(value, "prompt_version"),
        _string(value, "composition_fingerprint"),
        tuple(
            _string_value(item, "layer fingerprint")
            for item in _array(value, "layer_fingerprints")
        ),
    )


def _validation(value: JsonValue) -> ObservedValidationReceipt:
    from .contracts import ValidationReceiptSource

    raw = _as_mapping(value, "validation receipt")
    _exact(
        raw,
        {
            "step_id",
            "source",
            "validator_id",
            "validator_version",
            "passed",
            "disposition",
            "result_fingerprint",
        },
        "validation receipt",
    )
    passed = raw["passed"]
    if type(passed) is not bool:
        raise ValueError("validation passed must be boolean")
    return ObservedValidationReceipt(
        _string(raw, "step_id"), ValidationReceiptSource(_string(raw, "source")),
        _string(raw, "validator_id"), _string(raw, "validator_version"), passed,
        _string(raw, "result_fingerprint"), ValidatorDisposition(_string(raw, "disposition")),
    )


def _object(data: bytes, name: str) -> Mapping[str, JsonValue]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not valid JSON") from error
    return _as_mapping(freeze_json(cast(JsonValue, value)), name)


def _mapping(value: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    return _as_mapping(value[key], key)


def _as_mapping(value: JsonValue, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _array(value: Mapping[str, JsonValue], key: str) -> tuple[JsonValue, ...]:
    raw = value[key]
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{key} must be an array")
    return tuple(raw)


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    return _string_value(value[key], key)


def _string_value(value: JsonValue, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    _text(value, name)
    return value


def _optional_int(value: JsonValue, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or null")
    return value


def _exact(value: Mapping[str, JsonValue], fields: set[str], name: str) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} fields are not exact")


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 512:
        raise ValueError(f"{name} must be bounded trimmed text")


def _sha(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be lowercase sha256")


def _json_fingerprint(value: JsonValue) -> str:
    return _fingerprint("verified-child-json@1", freeze_json(value))


def verified_child_value_fingerprint(value: JsonValue) -> str:
    """Fingerprint one sanitized value using the proof codec domain."""

    return _json_fingerprint(value)


def _fingerprint(domain: str, value: JsonValue) -> str:
    encoded = json.dumps(
        _plain(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(domain.encode() + b"\0" + encoded).hexdigest()


def _plain(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value
