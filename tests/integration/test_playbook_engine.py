from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueStep,
    EngineErrorCode,
    PlaybookDefinition,
    PlaybookEngine,
    PlaybookEngineError,
    PlaybookRunStatus,
    ReadDependency,
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
ADAPTER = ArtifactReference("scripted_adapter", V1)
STATE = ArtifactReference("event_state", V1)
PROMPT = ArtifactReference("unused_prompt", V1)


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 10, 13, 0, tzinfo=UTC)


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
        raise AssertionError("dialogue flow must not call the model")

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        raise NotImplementedError

    async def cancel(self, token: CancellationToken) -> None:
        raise NotImplementedError


class RecordingTool:
    def __init__(self, name: str, calls: list[tuple[str, object]]) -> None:
        self._name = name
        self.calls = calls

    @property
    def name(self) -> str:
        return self._name

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls.append((self.name, arguments))
        return {"tool": self.name}


def make_dialogue_runtime() -> tuple[
    PlaybookEngine,
    SkillPackage,
    PlaybookDefinition,
    VersionPins,
    list[tuple[str, object]],
    Store,
]:
    calls: list[tuple[str, object]] = []
    question = DataReference(DataSourceKind.RUN_INPUT, "question")
    response = DataReference(DataSourceKind.STEP_OUTPUT, "clarification")
    definition = PlaybookDefinition(
        "dialogue_flow",
        V1,
        VersionRange(V1, V2),
        (
            ToolStep(
                "prepare",
                ArtifactReference("context.prepare", V1),
                {},
                "prepared",
                (DataBinding("question", question),),
            ),
            DialogueStep(
                "clarify",
                "Please clarify.",
                JsonSchema(
                    {
                        "type": "object",
                        "required": ("text",),
                        "properties": {"text": {"type": "string"}},
                        "additionalProperties": False,
                    }
                ),
                "clarification",
            ),
            ToolStep(
                "finish",
                ArtifactReference("answer.finish", V1),
                {},
                "finished",
                (DataBinding("clarification", response),),
            ),
        ),
        ("question",),
    )
    skill = SkillPackage(
        "dialogue_skill",
        V1,
        "Dialogue checkpoint fixture.",
        VersionRange(V1, V2),
        JsonSchema({"type": "object"}),
        JsonSchema({"type": "object"}),
        (
            PromptLayer(
                "policy",
                V1,
                PromptLayerKind.STUDY_SECURITY_POLICY,
                "Portable policy.",
            ),
        ),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (
            ToolRequirement("context.prepare", V1),
            ToolRequirement("answer.finish", V1),
        ),
        ArtifactReference(definition.id, definition.version),
    )
    pins = VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(definition.id, definition.version),
        PROMPT,
        (
            ToolBehaviorPin("context.prepare", V1),
            ToolBehaviorPin("answer.finish", V1),
        ),
        ADAPTER,
        STATE,
    )
    store = Store()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ADAPTER,
        state_contract=STATE,
        model=UnusedModel(),
        registries=RuntimeRegistries(
            (
                RecordingTool("context.prepare", calls),
                RecordingTool("answer.finish", calls),
            )
        ),
        run_store=store,
        clock=Clock(),
    )
    return engine, skill, definition, pins, calls, store


def test_dialogue_suspends_and_resume_continues_once_from_next_step() -> None:
    engine, skill, definition, pins, calls, _ = make_dialogue_runtime()
    dependency = (ReadDependency("source", "source-1", "checksum-1"),)
    run_id = RunId("run-dialogue")
    suspended = asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Ambiguous question"},
            pins=pins,
            read_dependencies=dependency,
        )
    )

    assert suspended.status is PlaybookRunStatus.SUSPENDED
    assert [name for name, _ in calls] == ["context.prepare"]

    completed = asyncio.run(
        engine.resume(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Ambiguous question"},
            pins=pins,
            read_dependencies=dependency,
            resume_input={"text": "Clarified"},
        )
    )

    assert completed.status is PlaybookRunStatus.COMPLETED
    assert [name for name, _ in calls] == ["context.prepare", "answer.finish"]
    assert completed.outputs["clarification"] == {"text": "Clarified"}
    assert [trace.step_id for trace in completed.traces].count("prepare") == 2
    assert [trace.step_id for trace in completed.traces].count("finish") == 2


def test_stale_resume_dependency_fails_before_any_resume_effect() -> None:
    engine, skill, definition, pins, calls, _ = make_dialogue_runtime()
    run_id = RunId("run-stale")
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
            read_dependencies=(ReadDependency("source", "source-1", "v1"),),
        )
    )
    effects_before_resume = list(calls)

    with pytest.raises(PlaybookEngineError) as caught:
        asyncio.run(
            engine.resume(
                run_id=run_id,
                skill=skill,
                definition=definition,
                inputs={"question": "Question"},
                pins=pins,
                read_dependencies=(ReadDependency("source", "source-1", "v2"),),
                resume_input={"text": "Clarified"},
            )
        )

    assert caught.value.failure.code is EngineErrorCode.STALE_READ_DEPENDENCY
    assert calls == effects_before_resume


def test_invalid_dialogue_response_does_not_claim_suspended_run() -> None:
    engine, skill, definition, pins, calls, _ = make_dialogue_runtime()
    run_id = RunId("run-invalid-dialogue")
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
        )
    )
    before = list(calls)

    with pytest.raises(PlaybookEngineError) as invalid:
        asyncio.run(
            engine.resume(
                run_id=run_id,
                skill=skill,
                definition=definition,
                inputs={"question": "Question"},
                pins=pins,
                read_dependencies=(),
                resume_input={"wrong": "field"},
            )
        )
    assert invalid.value.failure.code is EngineErrorCode.SCHEMA_ERROR
    assert calls == before

    completed = asyncio.run(
        engine.resume(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
            read_dependencies=(),
            resume_input={"text": "Valid"},
        )
    )
    assert completed.status is PlaybookRunStatus.COMPLETED


def test_second_resume_is_rejected_without_repeating_effects() -> None:
    engine, skill, definition, pins, calls, _ = make_dialogue_runtime()
    run_id = RunId("run-second-resume")
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
        )
    )
    asyncio.run(
        engine.resume(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
            read_dependencies=(),
            resume_input={"text": "First"},
        )
    )
    effects = list(calls)

    with pytest.raises(PlaybookEngineError) as second:
        asyncio.run(
            engine.resume(
                run_id=run_id,
                skill=skill,
                definition=definition,
                inputs={"question": "Question"},
                pins=pins,
                read_dependencies=(),
                resume_input={"text": "Second"},
            )
        )
    assert second.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert calls == effects


def test_process_loss_recovers_completed_run_without_repeating_effects() -> None:
    engine, skill, definition, pins, calls, store = make_dialogue_runtime()
    run_id = RunId("run-process-loss-recovery")
    inputs = {"question": "Question"}
    dependency = (ReadDependency("source", "source-1", "v1"),)
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs=inputs,
            pins=pins,
            read_dependencies=dependency,
        )
    )
    asyncio.run(
        engine.resume(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs=inputs,
            pins=pins,
            read_dependencies=dependency,
            resume_input={"text": "Clarified"},
        )
    )
    effects = list(calls)
    recovered_process = PlaybookEngine(
        engine_version=V1,
        model_adapter=ADAPTER,
        state_contract=STATE,
        model=UnusedModel(),
        registries=RuntimeRegistries(
            (
                RecordingTool("context.prepare", calls),
                RecordingTool("answer.finish", calls),
            )
        ),
        run_store=store,
        clock=Clock(),
    )

    recovered = recovered_process.recover(
        run_id=run_id,
        definition=definition,
        inputs=inputs,
        pins=pins,
        read_dependencies=dependency,
    )

    assert recovered.status is PlaybookRunStatus.COMPLETED
    assert recovered.outputs["clarification"] == {"text": "Clarified"}
    assert recovered.outputs["finished"] == {"tool": "answer.finish"}
    assert calls == effects


@pytest.mark.parametrize(
    "tamper",
    ["run_id", "schema", "fingerprint", "outputs", "traces"],
)
def test_tampered_checkpoint_is_rejected_before_resume_effects(tamper: str) -> None:
    engine, skill, definition, pins, calls, store = make_dialogue_runtime()
    run_id = RunId(f"run-tampered-{tamper}")
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
        )
    )
    payload = json.loads(store.data[run_id])
    if tamper == "run_id":
        payload["checkpoint"]["run_id"] = "different-run"
    elif tamper == "schema":
        payload["checkpoint"]["schema_version"] = 999
    elif tamper == "fingerprint":
        payload["definition_fingerprint"] = "0" * 64
    elif tamper == "outputs":
        payload["checkpoint"]["outputs"]["forged"] = True
    else:
        payload["traces"].pop()
    store.data[run_id] = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    effects = list(calls)

    with pytest.raises(PlaybookEngineError) as caught:
        asyncio.run(
            engine.resume(
                run_id=run_id,
                skill=skill,
                definition=definition,
                inputs={"question": "Question"},
                pins=pins,
                read_dependencies=(),
                resume_input={"text": "Response"},
            )
        )
    assert caught.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert calls == effects


def test_same_version_definition_content_change_is_rejected() -> None:
    engine, skill, definition, pins, calls, _ = make_dialogue_runtime()
    run_id = RunId("run-definition-change")
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs={"question": "Question"},
            pins=pins,
        )
    )
    dialogue = definition.steps[1]
    assert isinstance(dialogue, DialogueStep)
    changed = replace(
        definition,
        steps=(
            definition.steps[0],
            replace(dialogue, request_text="Changed request."),
            definition.steps[2],
        ),
    )

    with pytest.raises(PlaybookEngineError) as caught:
        asyncio.run(
            engine.resume(
                run_id=run_id,
                skill=skill,
                definition=changed,
                inputs={"question": "Question"},
                pins=pins,
                read_dependencies=(),
                resume_input={"text": "Response"},
            )
        )
    assert caught.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert [name for name, _ in calls] == ["context.prepare"]
