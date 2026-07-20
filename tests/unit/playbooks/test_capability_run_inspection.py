from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    DialogueStep,
    EngineErrorCode,
    InspectedRunRecord,
    PlaybookDefinition,
    PlaybookEngine,
    PlaybookEngineError,
    PlaybookRunResult,
    PlaybookRunStatus,
    ReadDependency,
    RunStatus,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolStep,
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
    VersionRange,
)

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
ADAPTER = ArtifactReference("unused_model", V1)
STATE = ArtifactReference("event_state", V1)
DEPENDENCY = (ReadDependency("course", "course-1", "sequence-1"),)
INPUTS: JsonObject = {"course_id": "course-1"}


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 15, 10, tzinfo=UTC)


class MemoryRunStore:
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
        raise AssertionError(f"model should not run: {request}")

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        raise AssertionError(f"model should not stream: {request}")

    async def cancel(self, token: CancellationToken) -> None:
        raise AssertionError(f"model should not cancel: {token}")


class EffectTool:
    def __init__(self, effects: list[str], result: JsonObject | BaseException) -> None:
        self.effects = effects
        self.result = result

    @property
    def name(self) -> str:
        return "fixture.effect"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        assert arguments == {}
        self.effects.append("effect")
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _definition(*, dialogue: bool = False) -> PlaybookDefinition:
    step = (
        DialogueStep(
            "clarify_goal",
            "Which learning goal should we focus on?",
            JsonSchema(
                {
                    "type": "object",
                    "required": ("text",),
                    "properties": {"text": {"type": "string"}},
                    "additionalProperties": False,
                }
            ),
            "clarification",
        )
        if dialogue
        else ToolStep(
            "perform",
            ArtifactReference("fixture.effect", V1),
            {},
            "result",
        )
    )
    return PlaybookDefinition(
        "inspection_flow",
        V1,
        VersionRange(V1, V2),
        (step,),
        ("course_id",),
    )


def _skill(definition: PlaybookDefinition, *, dialogue: bool = False) -> SkillPackage:
    return SkillPackage(
        "inspection_fixture",
        V1,
        "Inspect persisted runs without effects.",
        VersionRange(V1, V2),
        JsonSchema({"type": "object"}),
        JsonSchema({"type": "object"}),
        (
            PromptLayer(
                "policy", V1, PromptLayerKind.STUDY_SECURITY_POLICY, "Test policy."
            ),
        ),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        () if dialogue else (ToolRequirement("fixture.effect", V1),),
        ArtifactReference(definition.id, definition.version),
    )


def _pins(definition: PlaybookDefinition, *, dialogue: bool = False) -> VersionPins:
    return VersionPins(
        ArtifactReference("inspection_fixture", V1),
        ArtifactReference(definition.id, definition.version),
        ArtifactReference("inspection_prompt", V1),
        () if dialogue else (ToolBehaviorPin("fixture.effect", V1),),
        ADAPTER,
        STATE,
    )


def _engine(
    store: MemoryRunStore,
    effects: list[str],
    result: JsonObject | BaseException | None = None,
) -> PlaybookEngine:
    resolved_result: JsonObject | BaseException = (
        {"ok": True} if result is None else result
    )
    return PlaybookEngine(
        engine_version=V1,
        model_adapter=ADAPTER,
        state_contract=STATE,
        model=UnusedModel(),
        registries=RuntimeRegistries((EffectTool(effects, resolved_result),)),
        run_store=store,
        clock=Clock(),
    )


def _execute(
    engine: PlaybookEngine,
    run_id: RunId,
    definition: PlaybookDefinition,
    *,
    dialogue: bool = False,
) -> PlaybookRunResult:
    return asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=_skill(definition, dialogue=dialogue),
            definition=definition,
            inputs=INPUTS,
            pins=_pins(definition, dialogue=dialogue),
            read_dependencies=DEPENDENCY,
        )
    )


def _inspect(
    engine: PlaybookEngine,
    run_id: RunId,
    definition: PlaybookDefinition,
    *,
    dialogue: bool = False,
) -> InspectedRunRecord:
    return engine.inspect(
        run_id=run_id,
        definition=definition,
    )


def test_completed_and_failed_inspection_is_immutable_and_effect_free() -> None:
    definition = _definition()
    cases = (
        (
            RunId("completed"),
            {"ok": True},
            PlaybookRunStatus.COMPLETED,
            RunStatus.COMPLETED,
        ),
        (
            RunId("failed"),
            RuntimeError("boom"),
            PlaybookRunStatus.FAILED,
            RunStatus.FAILED,
        ),
    )
    for run_id, result, result_status, checkpoint_status in cases:
        store = MemoryRunStore()
        effects: list[str] = []
        engine = _engine(store, effects, result)
        executed = _execute(engine, run_id, definition)
        assert executed.status is result_status
        count = len(effects)
        first = _inspect(engine, run_id, definition)
        second = _inspect(engine, run_id, definition)
        assert first == second
        assert first.status is checkpoint_status
        assert first.inputs == INPUTS
        assert first.pins == _pins(definition)
        assert first.read_dependencies == DEPENDENCY
        assert first.checkpoint_fingerprint == second.checkpoint_fingerprint
        assert len(first.checkpoint_fingerprint) == 64
        assert len(effects) == count
        if checkpoint_status is RunStatus.FAILED:
            with pytest.raises(PlaybookEngineError, match="successful"):
                engine.recover(
                    run_id=run_id,
                    definition=definition,
                    inputs=INPUTS,
                    pins=_pins(definition),
                    read_dependencies=DEPENDENCY,
                )


def test_suspended_inspection_exposes_exact_dialogue_and_recover_rejects() -> None:
    definition = _definition(dialogue=True)
    store = MemoryRunStore()
    effects: list[str] = []
    engine = _engine(store, effects)
    run_id = RunId("suspended")
    result = _execute(engine, run_id, definition, dialogue=True)
    assert result.status is PlaybookRunStatus.SUSPENDED
    inspected = _inspect(engine, run_id, definition, dialogue=True)
    assert inspected.status is RunStatus.SUSPENDED
    assert inspected.next_step_index == 1
    assert inspected.dialogue_step_id == "clarify_goal"
    assert inspected.dialogue_request == "Which learning goal should we focus on?"
    assert inspected.checkpoint_fingerprint == _inspect(
        engine, run_id, definition, dialogue=True
    ).checkpoint_fingerprint
    assert effects == []
    with pytest.raises(PlaybookEngineError) as error:
        engine.recover(
            run_id=run_id,
            definition=definition,
            inputs=INPUTS,
            pins=_pins(definition, dialogue=True),
            read_dependencies=DEPENDENCY,
        )
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT


def test_ambiguous_async_cancellation_stays_running_and_recover_rejects() -> None:
    definition = _definition()
    store = MemoryRunStore()
    effects: list[str] = []
    engine = _engine(store, effects, asyncio.CancelledError())
    run_id = RunId("ambiguous-running")
    with pytest.raises(asyncio.CancelledError):
        _execute(engine, run_id, definition)
    inspected = _inspect(engine, run_id, definition)
    assert inspected.status is RunStatus.RUNNING
    assert effects == ["effect"]
    with pytest.raises(PlaybookEngineError) as error:
        engine.recover(
            run_id=run_id,
            definition=definition,
            inputs=INPUTS,
            pins=_pins(definition),
            read_dependencies=DEPENDENCY,
        )
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT


def test_inspection_exposes_persisted_bindings_and_rejects_definition_or_payload_tamper() -> None:
    definition = _definition()
    store = MemoryRunStore()
    engine = _engine(store, [])
    run_id = RunId("binding-check")
    _execute(engine, run_id, definition)

    inspected = _inspect(engine, run_id, definition)
    assert inspected.inputs == INPUTS
    assert inspected.pins == _pins(definition)
    assert inspected.read_dependencies == DEPENDENCY

    incompatible = replace(definition, id="other_flow")
    with pytest.raises(PlaybookEngineError) as mismatch:
        engine.inspect(run_id=run_id, definition=incompatible)
    assert mismatch.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT

    store.data[run_id] = store.data[run_id][:-1] + b"!"
    with pytest.raises(PlaybookEngineError) as error:
        _inspect(engine, run_id, definition)
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
