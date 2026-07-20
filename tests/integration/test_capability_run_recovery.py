from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from study_agent.domain import RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    CancelledRunResult,
    EngineErrorCode,
    FailedRunResult,
    InspectedRunRecord,
    ModelStep,
    PlaybookDefinition,
    PlaybookEngine,
    PlaybookEngineError,
    PlaybookRunResult,
    PlaybookRunStatus,
    RunStatus,
    RuntimeRegistries,
    StepTraceStatus,
    VersionPins,
)
from study_agent.ports import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelFinishReason,
    ModelInvocation,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
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
    VersionRange,
)

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
ADAPTER = ArtifactReference("cancel_model", V1)
STATE = ArtifactReference("event_state", V1)
PROMPT = ArtifactReference("cancel_prompt", V1)
INPUTS: JsonObject = {"course_id": "course-1"}


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 15, 11, tzinfo=UTC)


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


class ScriptedModel:
    def __init__(self, outcome: ModelResponse | BaseException) -> None:
        self.outcome = outcome
        self.calls = 0

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(structured_output=True)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        assert request.messages
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        raise AssertionError(f"stream should not be used: {request}")

    async def cancel(self, token: CancellationToken) -> None:
        raise AssertionError(f"cancel should not be called: {token}")


def _definition() -> PlaybookDefinition:
    return PlaybookDefinition(
        "model_cancel_flow",
        V1,
        VersionRange(V1, V2),
        (
            ModelStep(
                "respond",
                PROMPT,
                ModelRequest((ModelMessage(MessageRole.USER, "Respond."),)),
                JsonSchema(
                    {
                        "type": "object",
                        "required": ("answer",),
                        "properties": {"answer": {"type": "string"}},
                        "additionalProperties": False,
                    }
                ),
                "answer",
            ),
        ),
        ("course_id",),
    )


def _skill(definition: PlaybookDefinition) -> SkillPackage:
    return SkillPackage(
        "model_cancel_fixture",
        V1,
        "Verify truthful model cancellation.",
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
        (),
        ArtifactReference(definition.id, definition.version),
    )


def _pins(definition: PlaybookDefinition) -> VersionPins:
    return VersionPins(
        ArtifactReference("model_cancel_fixture", V1),
        ArtifactReference(definition.id, definition.version),
        PROMPT,
        (),
        ADAPTER,
        STATE,
    )


def _response(reason: ModelFinishReason) -> ModelResponse:
    return ModelResponse(
        "cancel response",
        ModelUsage(1, 1),
        reason,
        ModelInvocation("cancel_model", "1.0.0", "fixture-model", "response-1"),
        structured_output={"answer": "unused"},
    )


def _engine(
    outcome: ModelResponse | BaseException,
) -> tuple[PlaybookEngine, ScriptedModel, MemoryRunStore]:
    model = ScriptedModel(outcome)
    store = MemoryRunStore()
    return (
        PlaybookEngine(
            engine_version=V1,
            model_adapter=ADAPTER,
            state_contract=STATE,
            model=model,
            registries=RuntimeRegistries(),
            run_store=store,
            clock=Clock(),
        ),
        model,
        store,
    )


def _execute(engine: PlaybookEngine, run_id: RunId) -> PlaybookRunResult:
    definition = _definition()
    return asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=_skill(definition),
            definition=definition,
            inputs=INPUTS,
            pins=_pins(definition),
        )
    )


def _inspect(engine: PlaybookEngine, run_id: RunId) -> InspectedRunRecord:
    definition = _definition()
    return engine.inspect(
        run_id=run_id,
        definition=definition,
    )


@pytest.mark.parametrize(
    "outcome",
    (
        ModelError(ModelErrorCode.CANCELLED, "transport confirmed cancellation"),
        _response(ModelFinishReason.CANCELLED),
    ),
)
def test_confirmed_model_cancellation_persists_cancelled_result_and_trace(
    outcome: ModelResponse | BaseException,
) -> None:
    engine, model, _ = _engine(outcome)
    run_id = RunId("confirmed-cancel")
    result = _execute(engine, run_id)
    assert isinstance(result, CancelledRunResult)
    assert result.status is PlaybookRunStatus.CANCELLED
    assert result.failure.code is EngineErrorCode.CANCELLED
    assert result.traces[-1].status is StepTraceStatus.CANCELLED

    inspected = _inspect(engine, run_id)
    assert inspected.status is RunStatus.CANCELLED
    assert inspected.traces == result.traces
    assert model.calls == 1
    with pytest.raises(PlaybookEngineError) as error:
        engine.recover(
            run_id=run_id,
            definition=_definition(),
            inputs=INPUTS,
            pins=_pins(_definition()),
        )
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert model.calls == 1


def test_generic_model_error_is_failed_not_cancelled() -> None:
    engine, model, _ = _engine(
        ModelError(ModelErrorCode.TIMEOUT, "timeout", retryable=True)
    )
    run_id = RunId("failed-model")
    result = _execute(engine, run_id)
    assert isinstance(result, FailedRunResult)
    assert result.status is PlaybookRunStatus.FAILED
    assert result.failure.code is EngineErrorCode.MODEL_ERROR
    assert result.traces[-1].status is StepTraceStatus.FAILED
    assert _inspect(engine, run_id).status is RunStatus.FAILED
    assert model.calls == 1


def test_asyncio_cancelled_error_propagates_and_remains_ambiguous_running() -> None:
    engine, model, _ = _engine(asyncio.CancelledError())
    run_id = RunId("process-cancelled")
    with pytest.raises(asyncio.CancelledError):
        _execute(engine, run_id)
    inspected = _inspect(engine, run_id)
    assert inspected.status is RunStatus.RUNNING
    assert inspected.traces == ()
    assert model.calls == 1
    with pytest.raises(PlaybookEngineError) as error:
        engine.recover(
            run_id=run_id,
            definition=_definition(),
            inputs=INPUTS,
            pins=_pins(_definition()),
        )
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
    assert model.calls == 1


def test_cancelled_finish_with_mismatched_invocation_is_failed_model_error() -> None:
    response = ModelResponse(
        "cancel response",
        ModelUsage(1, 1),
        ModelFinishReason.CANCELLED,
        ModelInvocation("wrong-adapter", "1.0.0", "fixture-model", "response-2"),
        structured_output={"answer": "unused"},
    )
    engine, model, _ = _engine(response)
    run_id = RunId("cancelled-wrong-provenance")
    result = _execute(engine, run_id)
    assert isinstance(result, FailedRunResult)
    assert result.status is PlaybookRunStatus.FAILED
    assert result.failure.code is EngineErrorCode.MODEL_ERROR
    assert result.traces[-1].status is StepTraceStatus.FAILED
    assert _inspect(engine, run_id).status is RunStatus.FAILED
    assert model.calls == 1


def test_tampered_cancelled_terminal_error_receipt_is_rejected() -> None:
    engine, _, store = _engine(
        ModelError(ModelErrorCode.CANCELLED, "transport confirmed cancellation")
    )
    run_id = RunId("tampered-cancelled")
    result = _execute(engine, run_id)
    assert isinstance(result, CancelledRunResult)

    payload = json.loads(store.data[run_id])
    payload["traces"][-1]["details"]["error_code"] = "model_error"
    store.data[run_id] = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(PlaybookEngineError) as error:
        _inspect(engine, run_id)
    assert error.value.failure.code is EngineErrorCode.INCOMPATIBLE_CHECKPOINT
