from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

import pytest

from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.playbooks import (
    CompletedRunResult,
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueGate,
    DialogueStep,
    EngineErrorCode,
    FailedRunResult,
    PlaybookDefinition,
    PlaybookEngine,
    PlaybookEngineError,
    PlaybookRunStatus,
    ReadDependency,
    RunStatus,
    RuntimeRegistries,
    StepTraceStatus,
    SuspendedRunResult,
    ToolBehaviorPin,
    ToolStep,
    ValidateStep,
    ValidationOutcome,
    ValidatorDisposition,
    VersionPins,
)
from study_agent.ports import (
    CancellationToken,
    ModelCapabilities,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)
from study_agent.skills import (
    ArtifactReference,
    GroundingPolicy,
    JsonSchema,
    PromptLayer,
    PromptLayerKind,
    SemanticVersion,
    SkillPackage,
    StateWritePolicy,
    ToolRequirement,
    ValidatorDefinition,
    VersionRange,
)

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
ADAPTER = ArtifactReference("fixture_model", V1)
STATE = ArtifactReference("event_state", V1)
PROMPT = ArtifactReference("fixture_prompt", V1)
INPUTS: JsonObject = {"question": "Explain the aortic valve."}
DEPENDENCIES = (ReadDependency("course", "course-1", "sequence-1"),)
DEFAULT_RESPONSE: JsonObject = {"text": "Use the explicit task."}
RESPONSE_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("text",),
        "properties": {"text": {"type": "string"}},
        "additionalProperties": False,
    }
)


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 15, 12, tzinfo=UTC)


class Store:
    def __init__(self) -> None:
        self.data: dict[RunId, bytes] = {}

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.data:
            return False
        self.data[run_id] = payload
        return True

    def compare_and_set(self, run_id: RunId, expected: bytes, replacement: bytes) -> bool:
        if self.data.get(run_id) != expected:
            return False
        self.data[run_id] = replacement
        return True

    def load(self, run_id: RunId) -> bytes:
        return self.data[run_id]


class UnusedModel:
    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities()

    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise AssertionError(f"optional dialogue must not call the model: {request}")

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        raise AssertionError(f"optional dialogue must not stream the model: {request}")

    async def cancel(self, token: CancellationToken) -> None:
        raise AssertionError(f"optional dialogue must not cancel the model: {token}")


class SeedTool:
    def __init__(self, calls: list[tuple[str, JsonObject]]) -> None:
        self.calls = calls

    @property
    def name(self) -> str:
        return "fixture.seed"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls.append((self.name, arguments))
        return {"seed": "ready"}


class FinishTool:
    def __init__(
        self, calls: list[tuple[str, JsonObject]], *, interrupt: bool = False
    ) -> None:
        self.calls = calls
        self.interrupt = interrupt

    @property
    def name(self) -> str:
        return "fixture.finish"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls.append((self.name, arguments))
        if self.interrupt:
            raise asyncio.CancelledError
        return {"answer": "Finished."}


class ReadinessValidator:
    def __init__(
        self,
        condition: JsonValue,
        calls: list[tuple[str, JsonObject]],
    ) -> None:
        self.condition = condition
        self.calls = calls

    @property
    def id(self) -> str:
        return "fixture.readiness"

    @property
    def version(self) -> SemanticVersion:
        return V1

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        self.calls.append((self.id, inputs))
        return ValidationOutcome(
            True,
            ValidatorDisposition.CONTINUE,
            {"result": {"needs_clarification": self.condition}},
        )


@dataclass(slots=True)
class Fixture:
    engine: PlaybookEngine
    skill: SkillPackage
    definition: PlaybookDefinition
    pins: VersionPins
    calls: list[tuple[str, JsonObject]]
    store: Store


def _definition(
    *,
    default_response: JsonValue = DEFAULT_RESPONSE,
    gated: bool = True,
) -> PlaybookDefinition:
    clarification = DataReference(DataSourceKind.STEP_OUTPUT, "clarification")
    gate = (
        DialogueGate(
            DataReference(
                DataSourceKind.STEP_OUTPUT,
                "readiness",
                ("result", "needs_clarification"),
            ),
            default_response,
        )
        if gated
        else None
    )
    return PlaybookDefinition(
        "optional_dialogue_flow",
        V1,
        VersionRange(V1, V2),
        (
            ToolStep(
                "seed",
                ArtifactReference("fixture.seed", V1),
                {},
                "seed",
            ),
            ValidateStep(
                "readiness",
                ArtifactReference("fixture.readiness", V1),
                ("seed",),
                "readiness",
            ),
            DialogueStep(
                "clarify",
                "Which aspect should we focus on?",
                RESPONSE_SCHEMA,
                "clarification",
                gate,
            ),
            ToolStep(
                "finish",
                ArtifactReference("fixture.finish", V1),
                {},
                "finished",
                (DataBinding("clarification", clarification),),
            ),
        ),
        ("question",),
    )


def _skill(definition: PlaybookDefinition) -> SkillPackage:
    return SkillPackage(
        "optional_dialogue_skill",
        V1,
        "Exercise deterministic optional dialogue.",
        VersionRange(V1, V2),
        JsonSchema({"type": "object"}),
        JsonSchema({"type": "object"}),
        (
            PromptLayer(
                "policy",
                V1,
                PromptLayerKind.STUDY_SECURITY_POLICY,
                "Portable fixture policy.",
            ),
        ),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (
            ToolRequirement("fixture.seed", V1),
            ToolRequirement("fixture.finish", V1),
        ),
        ArtifactReference(definition.id, definition.version),
        validators=(
            ValidatorDefinition(
                "fixture.readiness",
                V1,
                "Decide whether clarification is necessary.",
            ),
        ),
    )


def _pins(definition: PlaybookDefinition) -> VersionPins:
    return VersionPins(
        ArtifactReference("optional_dialogue_skill", V1),
        ArtifactReference(definition.id, definition.version),
        PROMPT,
        (
            ToolBehaviorPin("fixture.seed", V1),
            ToolBehaviorPin("fixture.finish", V1),
        ),
        ADAPTER,
        STATE,
    )


def _fixture(
    condition: JsonValue,
    *,
    default_response: JsonValue = DEFAULT_RESPONSE,
    gated: bool = True,
    interrupt_finish: bool = False,
) -> Fixture:
    calls: list[tuple[str, JsonObject]] = []
    definition = _definition(default_response=default_response, gated=gated)
    store = Store()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ADAPTER,
        state_contract=STATE,
        model=UnusedModel(),
        registries=RuntimeRegistries(
            (
                SeedTool(calls),
                FinishTool(calls, interrupt=interrupt_finish),
            ),
            (ReadinessValidator(condition, calls),),
        ),
        run_store=store,
        clock=Clock(),
    )
    return Fixture(engine, _skill(definition), definition, _pins(definition), calls, store)


def _execute(
    fixture: Fixture, run_id: RunId
) -> CompletedRunResult | SuspendedRunResult | FailedRunResult:
    result = asyncio.run(
        fixture.engine.execute(
            run_id=run_id,
            skill=fixture.skill,
            definition=fixture.definition,
            inputs=INPUTS,
            pins=fixture.pins,
            read_dependencies=DEPENDENCIES,
        )
    )
    assert isinstance(result, CompletedRunResult | SuspendedRunResult | FailedRunResult)
    return result


def _resume(fixture: Fixture, run_id: RunId, response: JsonObject) -> CompletedRunResult:
    result = asyncio.run(
        fixture.engine.resume(
            run_id=run_id,
            skill=fixture.skill,
            definition=fixture.definition,
            inputs=INPUTS,
            pins=fixture.pins,
            read_dependencies=DEPENDENCIES,
            resume_input=response,
        )
    )
    assert isinstance(result, CompletedRunResult)
    return result


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _result_fingerprint(value: object) -> str:
    encoded = _canonical(value)
    return sha256(b"study-agent-json-result-v1\0" + encoded).hexdigest()


def _completed_trace(payload: dict[str, object], step_id: str) -> dict[str, object]:
    traces = cast(list[dict[str, object]], payload["traces"])
    return next(
        trace
        for trace in traces
        if trace["step_id"] == step_id and trace["status"] == "completed"
    )


def test_false_gate_skips_with_bound_default_and_recovers_without_ambiguity() -> None:
    fixture = _fixture(False)
    run_id = RunId("optional-skip")
    result = _execute(fixture, run_id)
    assert isinstance(result, CompletedRunResult)
    assert result.outputs["clarification"] == DEFAULT_RESPONSE
    assert [name for name, _ in fixture.calls] == [
        "fixture.seed",
        "fixture.readiness",
        "fixture.finish",
    ]
    finish_arguments = fixture.calls[-1][1]
    assert finish_arguments == {"clarification": DEFAULT_RESPONSE}
    dialogue_traces = tuple(trace for trace in result.traces if trace.step_id == "clarify")
    assert tuple(trace.status for trace in dialogue_traces) == (
        StepTraceStatus.STARTED,
        StepTraceStatus.COMPLETED,
    )
    assert dialogue_traces[-1].details["dialogue_disposition"] == "skipped"
    assert dialogue_traces[-1].details["output_fingerprint"] == _result_fingerprint(
        DEFAULT_RESPONSE
    )

    calls = list(fixture.calls)
    recovered = fixture.engine.recover(
        run_id=run_id,
        definition=fixture.definition,
        inputs=INPUTS,
        pins=fixture.pins,
        read_dependencies=DEPENDENCIES,
    )
    assert recovered.status is PlaybookRunStatus.COMPLETED
    assert recovered.outputs["clarification"] == DEFAULT_RESPONSE
    assert fixture.calls == calls


def test_true_gate_suspends_once_and_exact_resume_completes_once() -> None:
    fixture = _fixture(True)
    run_id = RunId("optional-suspend")
    suspended = _execute(fixture, run_id)
    assert isinstance(suspended, SuspendedRunResult)
    assert [name for name, _ in fixture.calls] == [
        "fixture.seed",
        "fixture.readiness",
    ]
    assert "clarification" not in suspended.outputs

    response: JsonObject = {"text": "Focus on the valve cusps."}
    completed = _resume(fixture, run_id, response)
    assert completed.outputs["clarification"] == response
    assert [name for name, _ in fixture.calls].count("fixture.finish") == 1
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as duplicate:
        asyncio.run(
            fixture.engine.resume(
                run_id=run_id,
                skill=fixture.skill,
                definition=fixture.definition,
                inputs=INPUTS,
                pins=fixture.pins,
                read_dependencies=DEPENDENCIES,
                resume_input=response,
            )
        )
    assert duplicate.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert fixture.calls == calls


def test_wrong_condition_type_fails_closed_and_duplicate_run_repeats_no_effects() -> None:
    fixture = _fixture("yes")
    run_id = RunId("optional-wrong-condition")
    result = _execute(fixture, run_id)
    assert isinstance(result, FailedRunResult)
    assert result.failure.code is EngineErrorCode.BINDING_ERROR
    assert [name for name, _ in fixture.calls] == [
        "fixture.seed",
        "fixture.readiness",
    ]
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as duplicate:
        _execute(fixture, run_id)
    assert duplicate.value.failure.code is EngineErrorCode.DUPLICATE_RUN
    assert fixture.calls == calls


def test_invalid_default_fails_preflight_before_executor_or_checkpoint_effects() -> None:
    fixture = _fixture(False, default_response={"wrong": "shape"})
    run_id = RunId("optional-invalid-default")
    with pytest.raises(PlaybookEngineError) as invalid:
        _execute(fixture, run_id)
    assert invalid.value.failure.code is EngineErrorCode.SCHEMA_ERROR
    assert fixture.calls == []
    assert run_id not in fixture.store.data


def test_process_interruption_after_resume_remains_ambiguous_and_single_effect() -> None:
    fixture = _fixture(True, interrupt_finish=True)
    run_id = RunId("optional-interrupted-resume")
    assert isinstance(_execute(fixture, run_id), SuspendedRunResult)
    response: JsonObject = {"text": "Focus on the cusps."}
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            fixture.engine.resume(
                run_id=run_id,
                skill=fixture.skill,
                definition=fixture.definition,
                inputs=INPUTS,
                pins=fixture.pins,
                read_dependencies=DEPENDENCIES,
                resume_input=response,
            )
        )
    inspected = fixture.engine.inspect(run_id=run_id, definition=fixture.definition)
    assert inspected.status is RunStatus.RUNNING
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as retry:
        asyncio.run(
            fixture.engine.resume(
                run_id=run_id,
                skill=fixture.skill,
                definition=fixture.definition,
                inputs=INPUTS,
                pins=fixture.pins,
                read_dependencies=DEPENDENCIES,
                resume_input=response,
            )
        )
    assert retry.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert fixture.calls == calls


@pytest.mark.parametrize(
    "tamper",
    ("condition", "disposition", "default", "output_fingerprint"),
)
def test_skipped_recovery_rejects_semantic_tamper_without_effects(tamper: str) -> None:
    fixture = _fixture(False)
    run_id = RunId(f"optional-skip-tamper-{tamper}")
    assert isinstance(_execute(fixture, run_id), CompletedRunResult)
    payload = cast(dict[str, object], json.loads(fixture.store.data[run_id]))
    checkpoint = cast(dict[str, object], payload["checkpoint"])
    outputs = cast(dict[str, object], checkpoint["outputs"])
    dialogue = _completed_trace(payload, "clarify")
    details = cast(dict[str, object], dialogue["details"])
    if tamper == "condition":
        readiness = cast(dict[str, object], outputs["readiness"])
        result = cast(dict[str, object], readiness["result"])
        result["needs_clarification"] = True
        validator = _completed_trace(payload, "readiness")
        validator_details = cast(dict[str, object], validator["details"])
        receipt = cast(dict[str, object], validator_details["validator"])
        fingerprint = _result_fingerprint(readiness)
        validator_details["output_fingerprint"] = fingerprint
        receipt["result_fingerprint"] = fingerprint
    elif tamper == "disposition":
        details["dialogue_disposition"] = "resumed"
    elif tamper == "default":
        outputs["clarification"] = {"text": "Forged default."}
        details["output_fingerprint"] = _result_fingerprint(outputs["clarification"])
    else:
        details["output_fingerprint"] = "0" * 64
    fixture.store.data[run_id] = _canonical(payload)
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as rejected:
        fixture.engine.recover(
            run_id=run_id,
            definition=fixture.definition,
            inputs=INPUTS,
            pins=fixture.pins,
            read_dependencies=DEPENDENCIES,
        )
    assert rejected.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert fixture.calls == calls


def test_resumed_generation_and_canonical_payload_tamper_fail_closed() -> None:
    fixture = _fixture(True)
    run_id = RunId("optional-resume-generation-tamper")
    assert isinstance(_execute(fixture, run_id), SuspendedRunResult)
    _resume(fixture, run_id, {"text": "Focus on cusps."})
    payload = cast(dict[str, object], json.loads(fixture.store.data[run_id]))
    dialogue = _completed_trace(payload, "clarify")
    details = cast(dict[str, object], dialogue["details"])
    details["resume_generation_fingerprint"] = "0" * 64
    fixture.store.data[run_id] = _canonical(payload)
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as generation:
        fixture.engine.recover(
            run_id=run_id,
            definition=fixture.definition,
            inputs=INPUTS,
            pins=fixture.pins,
            read_dependencies=DEPENDENCIES,
        )
    assert generation.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert fixture.calls == calls

    timestamp_fixture = _fixture(True)
    timestamp_run = RunId("optional-resume-timestamp-tamper")
    assert isinstance(_execute(timestamp_fixture, timestamp_run), SuspendedRunResult)
    _resume(timestamp_fixture, timestamp_run, {"text": "Focus on cusps."})
    timestamp_payload = cast(
        dict[str, object], json.loads(timestamp_fixture.store.data[timestamp_run])
    )
    timestamp_dialogue = _completed_trace(timestamp_payload, "clarify")
    timestamp_details = cast(dict[str, object], timestamp_dialogue["details"])
    timestamp_details["resume_generation_updated_at"] = "2026-07-15T13:00:00+00:00"
    timestamp_fixture.store.data[timestamp_run] = _canonical(timestamp_payload)
    timestamp_calls = list(timestamp_fixture.calls)
    with pytest.raises(PlaybookEngineError) as timestamp:
        timestamp_fixture.engine.recover(
            run_id=timestamp_run,
            definition=timestamp_fixture.definition,
            inputs=INPUTS,
            pins=timestamp_fixture.pins,
            read_dependencies=DEPENDENCIES,
        )
    assert timestamp.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert timestamp_fixture.calls == timestamp_calls

    canonical_fixture = _fixture(False)
    canonical_run = RunId("optional-noncanonical-payload")
    assert isinstance(_execute(canonical_fixture, canonical_run), CompletedRunResult)
    decoded = json.loads(canonical_fixture.store.data[canonical_run])
    canonical_fixture.store.data[canonical_run] = json.dumps(
        decoded, sort_keys=True, indent=2
    ).encode()
    effects = list(canonical_fixture.calls)
    with pytest.raises(PlaybookEngineError) as noncanonical:
        canonical_fixture.engine.inspect(
            run_id=canonical_run,
            definition=canonical_fixture.definition,
        )
    assert noncanonical.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert canonical_fixture.calls == effects


def test_gate_definition_change_is_fingerprint_bound_without_reexecution() -> None:
    fixture = _fixture(False)
    run_id = RunId("optional-definition-change")
    assert isinstance(_execute(fixture, run_id), CompletedRunResult)
    dialogue = fixture.definition.steps[2]
    assert isinstance(dialogue, DialogueStep)
    assert dialogue.gate is not None
    changed = replace(
        fixture.definition,
        steps=(
            *fixture.definition.steps[:2],
            replace(
                dialogue,
                gate=replace(
                    dialogue.gate,
                    default_response={"text": "Changed default."},
                ),
            ),
            fixture.definition.steps[3],
        ),
    )
    calls = list(fixture.calls)
    with pytest.raises(PlaybookEngineError) as mismatch:
        fixture.engine.inspect(run_id=run_id, definition=changed)
    assert mismatch.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert fixture.calls == calls


def test_unconditional_legacy_dialogue_keeps_fingerprint_and_receipt_shape() -> None:
    fixture = _fixture(True, gated=False)
    run_id = RunId("legacy-unconditional-dialogue")
    suspended = _execute(fixture, run_id)
    assert isinstance(suspended, SuspendedRunResult)
    inspected = fixture.engine.inspect(run_id=run_id, definition=fixture.definition)
    assert inspected.definition_fingerprint == (
        "6ba9c6dd6c4b3acc1c65aae5d0731a30fd3242527c9ba5ab206dcb38b2a2904d"
    )
    completed = _resume(fixture, run_id, {"text": "Legacy response."})
    dialogue = tuple(trace for trace in completed.traces if trace.step_id == "clarify")
    assert tuple(trace.status for trace in dialogue) == (
        StepTraceStatus.STARTED,
        StepTraceStatus.SUSPENDED,
        StepTraceStatus.COMPLETED,
    )
    assert set(dialogue[-1].details) == {
        "output_fingerprint",
        "resume_generation_fingerprint",
        "resume_generation_updated_at",
    }
    payload = cast(dict[str, object], json.loads(fixture.store.data[run_id]))
    legacy_dialogue = _completed_trace(payload, "clarify")
    legacy_details = cast(dict[str, object], legacy_dialogue["details"])
    legacy_details.pop("resume_generation_updated_at")
    fixture.store.data[run_id] = _canonical(payload)
    calls = list(fixture.calls)
    legacy_inspected = fixture.engine.inspect(
        run_id=run_id,
        definition=fixture.definition,
    )
    assert legacy_inspected.status is RunStatus.COMPLETED
    recovered = fixture.engine.recover(
        run_id=run_id,
        definition=fixture.definition,
        inputs=INPUTS,
        pins=fixture.pins,
        read_dependencies=DEPENDENCIES,
    )
    assert recovered.status is PlaybookRunStatus.COMPLETED
    assert fixture.calls == calls
