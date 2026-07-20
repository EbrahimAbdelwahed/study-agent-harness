"""Repeatable isolated capability-worker orchestration over an atomic byte store."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any, NoReturn, cast

from study_agent.capabilities.contracts import CapabilityContinuation, TutorCapabilityId
from study_agent.domain import CorrelationId, ExecutionContext, RunId
from study_agent.domain._validation import JsonObject, JsonValue, freeze_json, freeze_object
from study_agent.playbooks import ReadDependency
from study_agent.ports.worker import GenerationWorkerStore, IsolatedCapabilityRunPort
from study_agent.skills import SemanticVersion
from study_agent.state import canonical_json_bytes

from .contracts import (
    MAX_STORED_STATE_BYTES,
    ChildCapabilityObservation,
    GenerationWorkerReceipt,
    GenerationWorkerStatus,
    GenerationWorkerTask,
    fingerprint_execution_inputs,
    fingerprint_output,
    fingerprint_run,
    fingerprint_store_state,
    fingerprint_validations,
    pins_from_json,
    sanitize_failure_code,
)
from .view import WorkerCompactView, WorkerDetailView


class GenerationWorkerConflictError(RuntimeError):
    """The requested worker identity conflicts with durable state."""


@dataclass(frozen=True, slots=True)
class _StoredWorkerState:
    task_bytes: bytes
    task_fingerprint: str
    authority_fingerprint: str
    status: GenerationWorkerStatus
    generation: int = 0
    continuation: CapabilityContinuation | None = None
    response_bytes: bytes | None = None
    response_fingerprint: str | None = None
    receipt: GenerationWorkerReceipt | None = None
    receipt_fingerprint: str | None = None
    child_run_id: RunId | None = None
    validator_fingerprint: str | None = None
    run_fingerprint: str | None = None
    prompt_fingerprint: str | None = None
    verified_output: JsonValue | None = None

    def __post_init__(self) -> None:
        task = GenerationWorkerTask.from_bytes(self.task_bytes)
        if task.fingerprint != self.task_fingerprint:
            raise ValueError("stored worker task fingerprint is invalid")
        _require_sha256(self.authority_fingerprint, "stored authority fingerprint")
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("stored generation must be non-negative")
        suspended = self.status is GenerationWorkerStatus.SUSPENDED
        claimed = self.status is GenerationWorkerStatus.RESUME_CLAIMED
        terminal = self.status.is_terminal
        if (suspended or claimed) != (self.continuation is not None):
            raise ValueError("stored continuation does not match worker state")
        if self.continuation is not None and (
            self.continuation.capability_id is not task.capability_id
            or self.continuation.capability_version != task.capability_version
            or self.continuation.manifest_fingerprint != task.manifest_fingerprint
            or self.continuation.pins != task.pins
            or self.continuation.definition_fingerprint != task.definition_fingerprint
            or _public_execution_projection(task, self.continuation.inputs)
            != task.capability_inputs()
        ):
            raise ValueError("stored continuation does not match worker task")
        if claimed != (self.response_bytes is not None and self.response_fingerprint is not None):
            raise ValueError("stored response claim does not match worker state")
        if self.response_bytes is not None:
            response = _decode_json_value(self.response_bytes, "worker response")
            if _response_fingerprint(response) != self.response_fingerprint:
                raise ValueError("stored response fingerprint is invalid")
        if terminal != (self.receipt is not None):
            raise ValueError("stored terminal state does not match receipt")
        if terminal != (self.receipt_fingerprint is not None):
            raise ValueError("stored terminal state does not match receipt commitment")
        for commitment, name in (
            (self.validator_fingerprint, "validator fingerprint"),
            (self.run_fingerprint, "run fingerprint"),
        ):
            if terminal != (commitment is not None):
                raise ValueError(f"stored terminal state does not match {name} commitment")
        if terminal != (self.child_run_id is not None):
            raise ValueError("stored terminal state does not match child run commitment")
        if self.receipt is not None and self.receipt.status is not self.status:
            raise ValueError("stored receipt status differs from worker state")
        if self.receipt is not None:
            if self.receipt.fingerprint != self.receipt_fingerprint:
                raise ValueError("stored receipt fingerprint is invalid")
            if (
                self.receipt.task_id != task.task_id
                or self.receipt.task_kind is not task.task_kind
                or self.receipt.task_fingerprint != task.fingerprint
                or self.receipt.pins_fingerprint != task.pins_fingerprint
                or self.receipt.input_fingerprint != task.payload_fingerprint
                or self.receipt.child_run_id != self.child_run_id
                or self.receipt.validator_fingerprint != self.validator_fingerprint
                or self.receipt.run_fingerprint != self.run_fingerprint
                or self.receipt.prompt_fingerprint != self.prompt_fingerprint
            ):
                raise ValueError("stored receipt does not match worker task")
        if (self.status is GenerationWorkerStatus.COMPLETED) != (self.verified_output is not None):
            raise ValueError("only completed worker state carries verified output")
        if self.verified_output is not None:
            object.__setattr__(self, "verified_output", freeze_json(self.verified_output))
        if self.receipt is not None and fingerprint_output(self.verified_output) != (
            self.receipt.output_fingerprint
        ):
            raise ValueError("stored verified output does not match receipt")
        if len(self.to_bytes()) > MAX_STORED_STATE_BYTES:
            raise ValueError("stored worker state exceeds 512 KiB")

    @property
    def task(self) -> GenerationWorkerTask:
        return GenerationWorkerTask.from_bytes(self.task_bytes)

    @property
    def fingerprint(self) -> str:
        return fingerprint_store_state(self.to_json())

    def to_json(self) -> JsonObject:
        return freeze_object(
            {
                "task_bytes": base64.b64encode(self.task_bytes).decode("ascii"),
                "task_fingerprint": self.task_fingerprint,
                "authority_fingerprint": self.authority_fingerprint,
                "status": self.status.value,
                "generation": self.generation,
                "continuation": self.continuation.to_json() if self.continuation else None,
                "response_bytes": (
                    base64.b64encode(self.response_bytes).decode("ascii")
                    if self.response_bytes is not None
                    else None
                ),
                "response_fingerprint": self.response_fingerprint,
                "receipt": self.receipt.to_json() if self.receipt else None,
                "receipt_fingerprint": self.receipt_fingerprint,
                "child_run_id": str(self.child_run_id) if self.child_run_id else None,
                "validator_fingerprint": self.validator_fingerprint,
                "run_fingerprint": self.run_fingerprint,
                "prompt_fingerprint": self.prompt_fingerprint,
                "verified_output": self.verified_output,
            }
        )

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())

    @classmethod
    def from_bytes(cls, data: bytes) -> _StoredWorkerState:
        if len(data) > MAX_STORED_STATE_BYTES:
            raise ValueError("stored worker state exceeds 512 KiB")
        value = _decode_object(data, "worker state")
        _exact(
            value,
            {
                "task_bytes",
                "task_fingerprint",
                "authority_fingerprint",
                "status",
                "generation",
                "continuation",
                "response_bytes",
                "response_fingerprint",
                "receipt",
                "receipt_fingerprint",
                "child_run_id",
                "validator_fingerprint",
                "run_fingerprint",
                "prompt_fingerprint",
                "verified_output",
            },
            "worker state",
        )
        continuation_raw = value["continuation"]
        receipt_raw = value["receipt"]
        response_raw = value["response_bytes"]
        state = cls(
            task_bytes=_decode_base64(_string(value, "task_bytes"), "task_bytes"),
            task_fingerprint=_string(value, "task_fingerprint"),
            authority_fingerprint=_string(value, "authority_fingerprint"),
            status=GenerationWorkerStatus(_string(value, "status")),
            generation=_integer(value, "generation"),
            continuation=(
                _continuation_from_json(_as_mapping(continuation_raw, "continuation"))
                if continuation_raw is not None
                else None
            ),
            response_bytes=(
                _decode_base64(response_raw, "response_bytes")
                if isinstance(response_raw, str)
                else None
            ),
            response_fingerprint=_optional_string(value, "response_fingerprint"),
            receipt=(
                GenerationWorkerReceipt.from_json(_as_mapping(receipt_raw, "receipt"))
                if receipt_raw is not None
                else None
            ),
            receipt_fingerprint=_optional_string(value, "receipt_fingerprint"),
            child_run_id=(
                RunId(value["child_run_id"])
                if isinstance(value["child_run_id"], str)
                else None
            ),
            validator_fingerprint=_optional_string(value, "validator_fingerprint"),
            run_fingerprint=_optional_string(value, "run_fingerprint"),
            prompt_fingerprint=_optional_string(value, "prompt_fingerprint"),
            verified_output=value["verified_output"],
        )
        if state.to_bytes() != data:
            raise ValueError("worker state bytes are not canonical")
        return state


class GenerationWorkerService:
    """Run one pinned capability in an isolated, retry-stable child context."""

    def __init__(
        self,
        *,
        store: GenerationWorkerStore,
        isolated_runs: IsolatedCapabilityRunPort,
    ) -> None:
        self._store = store
        self._isolated_runs = isolated_runs

    async def start(
        self, task: GenerationWorkerTask, parent: ExecutionContext
    ) -> WorkerCompactView:
        if not isinstance(task, GenerationWorkerTask):
            raise TypeError("task must be GenerationWorkerTask")
        authority = generation_worker_authority_fingerprint(task, parent)
        pending = _StoredWorkerState(
            task_bytes=task.to_bytes(),
            task_fingerprint=task.fingerprint,
            authority_fingerprint=authority,
            status=GenerationWorkerStatus.PENDING,
        )
        if self._store.create(task.task_id, pending.to_bytes()):
            state = pending
            raw = pending.to_bytes()
        else:
            raw = self._store.load(task.task_id)
            state = _StoredWorkerState.from_bytes(raw)
            self._require_identity(state, task, authority)
        if state.status is GenerationWorkerStatus.PENDING:
            return await self._drive_start(state, raw, parent)
        if state.status is GenerationWorkerStatus.RESUME_CLAIMED:
            return await self._drive_resume(state, raw, parent)
        return _compact(state)

    async def resume(
        self,
        task_id: str,
        generation: int,
        response: JsonValue,
        parent: ExecutionContext,
    ) -> WorkerCompactView:
        raw = self._store.load(task_id)
        state = _StoredWorkerState.from_bytes(raw)
        authority = generation_worker_authority_fingerprint(state.task, parent)
        self._require_identity(state, state.task, authority)
        if type(generation) is not int or generation < 0:
            raise ValueError("generation must be a non-negative integer")
        if generation != state.generation:
            self._conflict("worker resume generation changed")
        if state.status.is_terminal:
            return _compact(state)
        frozen_response = freeze_json(response)
        response_bytes = _json_value_bytes(frozen_response)
        response_fingerprint = _response_fingerprint(frozen_response)
        if state.status is GenerationWorkerStatus.RESUME_CLAIMED:
            if (
                state.response_bytes != response_bytes
                or state.response_fingerprint != response_fingerprint
            ):
                self._conflict("a different response already owns this generation")
            return await self._drive_resume(state, raw, parent)
        if state.status is not GenerationWorkerStatus.SUSPENDED:
            self._conflict("worker is not suspended")
        claimed = replace(
            state,
            status=GenerationWorkerStatus.RESUME_CLAIMED,
            response_bytes=response_bytes,
            response_fingerprint=response_fingerprint,
        )
        if not self._store.compare_and_set(task_id, raw, claimed.to_bytes()):
            raced_raw = self._store.load(task_id)
            raced = _StoredWorkerState.from_bytes(raced_raw)
            self._require_identity(raced, state.task, authority)
            if raced.status.is_terminal:
                return _compact(raced)
            if (
                raced.status is not GenerationWorkerStatus.RESUME_CLAIMED
                or raced.generation != state.generation
                or raced.response_bytes != response_bytes
            ):
                self._conflict("worker resume generation was claimed concurrently")
            return await self._drive_resume(raced, raced_raw, parent)
        return await self._drive_resume(claimed, claimed.to_bytes(), parent)

    def detail(self, task_id: str, parent: ExecutionContext) -> WorkerDetailView:
        state = _StoredWorkerState.from_bytes(self._store.load(task_id))
        authority = generation_worker_authority_fingerprint(state.task, parent)
        self._require_identity(state, state.task, authority)
        if (
            state.status is not GenerationWorkerStatus.COMPLETED
            or state.receipt is None
            or state.verified_output is None
        ):
            self._conflict("verified worker detail is unavailable")
        return WorkerDetailView(state.receipt, state.verified_output)

    async def _drive_start(
        self, state: _StoredWorkerState, raw: bytes, parent: ExecutionContext
    ) -> WorkerCompactView:
        task = state.task
        observation = await self._isolated_runs.start(
            task, generation_worker_child_context(task, parent)
        )
        return self._persist_observation(state, raw, observation)

    async def _drive_resume(
        self, state: _StoredWorkerState, raw: bytes, parent: ExecutionContext
    ) -> WorkerCompactView:
        if state.continuation is None or state.response_bytes is None:
            raise ValueError("claimed resume state is incomplete")
        response = _decode_json_value(state.response_bytes, "worker response")
        observation = await self._isolated_runs.resume(
            state.task,
            state.continuation,
            response,
            generation_worker_child_context(state.task, parent),
        )
        return self._persist_observation(state, raw, observation)

    def _persist_observation(
        self,
        state: _StoredWorkerState,
        raw: bytes,
        observation: ChildCapabilityObservation,
    ) -> WorkerCompactView:
        task = state.task
        expected_run_id = state.continuation.run_id if state.continuation is not None else None
        failure = _observation_binding_failure(task, observation, expected_run_id)
        if failure is not None:
            replacement = _terminal_state(
                state, observation, GenerationWorkerStatus.FAILED, failure
            )
        elif observation.status is GenerationWorkerStatus.RUNNING:
            return _compact(state, running_id=observation.run_id)
        elif observation.status is GenerationWorkerStatus.SUSPENDED:
            assert observation.continuation is not None
            replacement = replace(
                state,
                status=GenerationWorkerStatus.SUSPENDED,
                generation=(
                    state.generation + 1
                    if state.status is GenerationWorkerStatus.RESUME_CLAIMED
                    else state.generation
                ),
                continuation=observation.continuation,
                response_bytes=None,
                response_fingerprint=None,
            )
        elif observation.status.is_terminal:
            replacement = _terminal_state(
                state,
                observation,
                observation.status,
                observation.failure_code,
            )
        else:  # pragma: no cover - closed by ChildCapabilityObservation
            raise ValueError("unsupported child observation status")

        replacement_raw = replacement.to_bytes()
        if self._store.compare_and_set(task.task_id, raw, replacement_raw):
            return _compact(replacement)
        raced = _StoredWorkerState.from_bytes(self._store.load(task.task_id))
        self._require_identity(raced, task, state.authority_fingerprint)
        if raced.to_bytes() == replacement_raw or raced.status.is_terminal:
            return _compact(raced)
        self._conflict("worker state changed concurrently")

    @staticmethod
    def _require_identity(
        state: _StoredWorkerState,
        task: GenerationWorkerTask,
        authority_fingerprint: str,
    ) -> None:
        if state.task_bytes != task.to_bytes() or state.task_fingerprint != task.fingerprint:
            raise GenerationWorkerConflictError("worker task bytes or pins changed")
        if state.authority_fingerprint != authority_fingerprint:
            raise GenerationWorkerConflictError("worker authority changed")

    @staticmethod
    def _conflict(message: str) -> NoReturn:
        raise GenerationWorkerConflictError(message)


def _observation_binding_failure(
    task: GenerationWorkerTask,
    observation: ChildCapabilityObservation,
    expected_run_id: RunId | None,
) -> str | None:
    if expected_run_id is not None and observation.run_id != expected_run_id:
        return "child_run_mismatch"
    if (
        observation.capability_id is not task.capability_id
        or observation.capability_version != task.capability_version
        or observation.manifest_fingerprint != task.manifest_fingerprint
        or observation.pins != task.pins
        or observation.definition_fingerprint != task.definition_fingerprint
        or observation.output_schema_fingerprint != task.output_schema_fingerprint
    ):
        return "child_binding_mismatch"
    if observation.status is GenerationWorkerStatus.SUSPENDED:
        continuation = observation.continuation
        if continuation is None or (
            continuation.capability_id is not task.capability_id
            or continuation.capability_version != task.capability_version
            or continuation.manifest_fingerprint != task.manifest_fingerprint
            or continuation.pins != task.pins
            or continuation.definition_fingerprint != task.definition_fingerprint
            or _public_execution_projection(task, continuation.inputs)
            != task.capability_inputs()
            or _observed_execution_fingerprint(observation, continuation.inputs)
            != fingerprint_execution_inputs(continuation.inputs)
        ):
            return "child_continuation_mismatch"
    if observation.status is GenerationWorkerStatus.COMPLETED:
        run = observation.verified_run
        prompt = observation.prompt
        expected = tuple(
            (item.step_id, item.source, item.validator_id, item.validator_version)
            for item in task.expected_validations
        )
        actual = tuple(
            (item.step_id, item.source, item.validator_id, item.validator_version)
            for item in observation.validations
        )
        if (
            run is None
            or run.pins != task.pins
            or run.definition_fingerprint != task.definition_fingerprint
            or _public_execution_projection(task, run.inputs) != task.capability_inputs()
            or _observed_execution_fingerprint(observation, run.inputs)
            != fingerprint_execution_inputs(run.inputs)
            or not all(
                item.passed and item.disposition.value == "continue"
                for item in observation.validations
            )
            or actual != expected
        ):
            return "child_validation_provenance_invalid"
        if (
            prompt is None
            or prompt.prompt_id != task.pins.prompt.id
            or prompt.prompt_version != str(task.pins.prompt.version)
        ):
            return "child_prompt_provenance_invalid"
    if observation.status in {
        GenerationWorkerStatus.COMPLETED,
        GenerationWorkerStatus.TERMINATED,
    }:
        run = observation.verified_run
        if (
            run is None
            or run.pins != task.pins
            or run.definition_fingerprint != task.definition_fingerprint
            or _public_execution_projection(task, run.inputs) != task.capability_inputs()
            or _observed_execution_fingerprint(observation, run.inputs)
            != fingerprint_execution_inputs(run.inputs)
        ):
            return "child_verified_run_provenance_invalid"
    return None


def _public_execution_projection(
    task: GenerationWorkerTask, execution_inputs: JsonObject
) -> JsonObject:
    public = task.capability_inputs()
    keys = set(execution_inputs)
    public_keys = set(public)
    if keys not in (public_keys, public_keys | {"profile_selection_receipt"}):
        return freeze_object({})
    return freeze_object({key: execution_inputs[key] for key in public})


def _observed_execution_fingerprint(
    observation: ChildCapabilityObservation, execution_inputs: JsonObject
) -> str | None:
    if observation.execution_input_fingerprint is not None:
        return observation.execution_input_fingerprint
    if "profile_selection_receipt" in execution_inputs:
        return None
    return fingerprint_execution_inputs(execution_inputs)


def _terminal_state(
    state: _StoredWorkerState,
    observation: ChildCapabilityObservation,
    status: GenerationWorkerStatus,
    failure_code: str | None,
) -> _StoredWorkerState:
    task = state.task
    if status is GenerationWorkerStatus.COMPLETED:
        output = observation.output
        prompt_fingerprint = (
            observation.prompt.composition_fingerprint if observation.prompt else None
        )
        safe_failure = None
    else:
        output = None
        prompt_fingerprint = None
        safe_failure = sanitize_failure_code(failure_code, status.value)
    receipt = GenerationWorkerReceipt(
        task_id=task.task_id,
        task_kind=task.task_kind,
        status=status,
        child_run_id=observation.run_id,
        task_fingerprint=task.fingerprint,
        pins_fingerprint=task.pins_fingerprint,
        input_fingerprint=task.payload_fingerprint,
        output_fingerprint=fingerprint_output(output),
        validator_fingerprint=fingerprint_validations(observation.validations),
        run_fingerprint=fingerprint_run(observation),
        prompt_fingerprint=prompt_fingerprint,
        failure_code=safe_failure,
    )
    return replace(
        state,
        status=status,
        continuation=None,
        response_bytes=None,
        response_fingerprint=None,
        receipt=receipt,
        receipt_fingerprint=receipt.fingerprint,
        child_run_id=receipt.child_run_id,
        validator_fingerprint=receipt.validator_fingerprint,
        run_fingerprint=receipt.run_fingerprint,
        prompt_fingerprint=receipt.prompt_fingerprint,
        verified_output=output,
    )


def _compact(state: _StoredWorkerState, *, running_id: RunId | None = None) -> WorkerCompactView:
    task = state.task
    receipt = state.receipt
    status = GenerationWorkerStatus.RUNNING if running_id is not None else state.status
    return WorkerCompactView(
        task_id=task.task_id,
        task_kind=task.task_kind,
        status=status,
        generation=state.generation,
        task_fingerprint=task.fingerprint,
        child_run_id=running_id
        or (
            receipt.child_run_id
            if receipt
            else (state.continuation.run_id if state.continuation else None)
        ),
        receipt_fingerprint=receipt.fingerprint if receipt else None,
        failure_code=receipt.failure_code if receipt else None,
        verified_detail_available=status is GenerationWorkerStatus.COMPLETED,
    )


def generation_worker_authority_fingerprint(
    task: GenerationWorkerTask, parent: ExecutionContext
) -> str:
    if not isinstance(parent, ExecutionContext):
        raise TypeError("parent must be ExecutionContext")
    missing = set(task.required_authority) - set(parent.requested_capabilities)
    if missing:
        raise GenerationWorkerConflictError("parent lacks worker-required authority")
    payload = freeze_object(
        {
            "principal_kind": parent.principal_kind.value,
            "principal_id": parent.principal_id,
            "course_id": str(parent.course_id),
            "session_id": str(parent.session_id) if parent.session_id else None,
            "required_authority": task.required_authority,
        }
    )
    return _fingerprint("generation-worker-authority@1", payload)


def generation_worker_child_context(
    task: GenerationWorkerTask, parent: ExecutionContext
) -> ExecutionContext:
    identity = freeze_object(
        {
            "task_id": task.task_id,
            "task_fingerprint": task.fingerprint,
            "capability_id": task.capability_id.value,
            "capability_version": str(task.capability_version),
            "manifest_fingerprint": task.manifest_fingerprint,
        }
    )
    correlation = _fingerprint("generation-worker-correlation@1", identity)
    idempotency = _fingerprint("generation-worker-child-retry@1", identity)
    return ExecutionContext(
        principal_kind=parent.principal_kind,
        principal_id=parent.principal_id,
        course_id=parent.course_id,
        correlation_id=CorrelationId(f"worker-correlation-sha256:{correlation}"),
        requested_capabilities=frozenset(task.required_authority),
        session_id=parent.session_id,
        model_run_id=None,
        idempotency_key=f"worker-child-sha256:{idempotency}",
    )


def _continuation_from_json(value: Mapping[str, JsonValue]) -> CapabilityContinuation:
    _exact(
        value,
        {
            "run_id",
            "capability_id",
            "capability_version",
            "manifest_fingerprint",
            "authority_fingerprint",
            "retry_identity_fingerprint",
            "definition_fingerprint",
            "checkpoint_fingerprint",
            "dialogue_step_id",
            "next_step_index",
            "inputs",
            "pins",
            "read_dependencies",
        },
        "capability continuation",
    )
    dependencies: list[ReadDependency] = []
    for item in _array(value, "read_dependencies"):
        raw = _as_mapping(item, "read dependency")
        _exact(raw, {"kind", "id", "version"}, "read dependency")
        dependencies.append(
            ReadDependency(_string(raw, "kind"), _string(raw, "id"), _string(raw, "version"))
        )
    return CapabilityContinuation(
        run_id=RunId(_string(value, "run_id")),
        capability_id=TutorCapabilityId(_string(value, "capability_id")),
        capability_version=SemanticVersion.parse(_string(value, "capability_version")),
        manifest_fingerprint=_string(value, "manifest_fingerprint"),
        authority_fingerprint=_string(value, "authority_fingerprint"),
        retry_identity_fingerprint=_string(value, "retry_identity_fingerprint"),
        definition_fingerprint=_string(value, "definition_fingerprint"),
        checkpoint_fingerprint=_string(value, "checkpoint_fingerprint"),
        dialogue_step_id=_string(value, "dialogue_step_id"),
        next_step_index=_integer(value, "next_step_index"),
        inputs=_mapping(value, "inputs"),
        pins=pins_from_json(_mapping(value, "pins")),
        read_dependencies=tuple(dependencies),
    )


def _json_value_bytes(value: JsonValue) -> bytes:
    return canonical_json_bytes(freeze_object({"value": value}))


def _decode_json_value(data: bytes, name: str) -> JsonValue:
    value = _decode_object(data, name)
    _exact(value, {"value"}, name)
    if canonical_json_bytes(value) != data:
        raise ValueError(f"{name} bytes are not canonical")
    return value["value"]


def _response_fingerprint(value: JsonValue) -> str:
    return _fingerprint("generation-worker-response@1", freeze_object({"value": value}))


def _fingerprint(domain: str, value: JsonObject) -> str:
    return sha256(domain.encode() + b"\0" + canonical_json_bytes(value)).hexdigest()


def _decode_object(data: bytes, name: str) -> JsonObject:
    try:
        decoded: Any = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} bytes are invalid JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError(f"{name} must be a JSON object")
    return freeze_object(cast(dict[str, JsonValue], decoded))


def _decode_base64(value: str, name: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError as error:
        raise ValueError(f"{name} is not canonical base64") from error
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{name} is not canonical base64")
    return decoded


def _exact(value: Mapping[str, JsonValue], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields must be exact")


def _as_mapping(value: JsonValue, name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return freeze_object(value)


def _mapping(value: Mapping[str, JsonValue], key: str) -> JsonObject:
    return _as_mapping(value[key], key)


def _array(value: Mapping[str, JsonValue], key: str) -> tuple[JsonValue, ...]:
    raw = value.get(key)
    if not isinstance(raw, tuple):
        raise ValueError(f"{key} must be an array")
    return raw


def _string(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    return raw


def _optional_string(value: Mapping[str, JsonValue], key: str) -> str | None:
    raw = value.get(key)
    if raw is not None and not isinstance(raw, str):
        raise ValueError(f"{key} must be a string or null")
    return raw


def _integer(value: Mapping[str, JsonValue], key: str) -> int:
    raw = value.get(key)
    if type(raw) is not int:
        raise ValueError(f"{key} must be an integer")
    return raw


def _require_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")
