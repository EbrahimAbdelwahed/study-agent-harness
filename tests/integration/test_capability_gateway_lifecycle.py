from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from study_agent.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityBinding,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CapabilityManifest,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    StudyCapabilityGateway,
    SuspendedCapabilityOutcome,
    TerminatedCapabilityOutcome,
    TutorCapabilityId,
)
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    ModelRunId,
    PrincipalKind,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    PlaybookEngine,
    PlaybookRunStatus,
    ReadDependency,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolStep,
    ValidateStep,
    ValidationOutcome,
    ValidatorDisposition,
    VersionPins,
)
from study_agent.ports import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
    ModelErrorCode,
    ModelMessage,
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
COURSE = CourseId("course-capability")
SESSION = SessionId("session-capability")
INPUTS: JsonObject = {"topic": "aortic valve"}
INPUT_SCHEMA: JsonObject = {
    "type": "object",
    "required": ("topic",),
    "properties": {"topic": {"type": "string"}},
    "additionalProperties": False,
}
OUTPUT_SCHEMA: JsonObject = {
    "type": "object",
    "required": ("answer",),
    "properties": {"answer": {"type": "string"}},
    "additionalProperties": False,
}


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 15, 12, tzinfo=UTC)


class MemoryRunStore:
    def __init__(self) -> None:
        self.data: dict[RunId, bytes] = {}
        self.cas_calls = 0
        self.converge_on_cas: int | None = None

    def create(self, run_id: RunId, payload: bytes) -> bool:
        if run_id in self.data:
            return False
        self.data[run_id] = payload
        return True

    def compare_and_set(self, run_id: RunId, expected: bytes, replacement: bytes) -> bool:
        self.cas_calls += 1
        if self.data.get(run_id) != expected:
            return False
        if self.converge_on_cas == self.cas_calls:
            self.converge_on_cas = None
            self.data[run_id] = replacement
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


class AnswerTool:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture.answer"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls += 1
        response = arguments.get("clarification")
        assert response == {"text": "focus on cusps"}
        return {"answer": "The aortic valve has three cusps."}


class Dependencies:
    def __init__(self, *, duplicate: bool = False, drift: bool = False) -> None:
        self.calls = 0
        self.duplicate = duplicate
        self.drift = drift

    def __call__(
        self, *, context: ExecutionContext, inputs: JsonObject
    ) -> tuple[ReadDependency, ...]:
        self.calls += 1
        assert context.course_id
        assert inputs == INPUTS
        version = "sequence-2" if self.drift and self.calls > 1 else "sequence-1"
        item = ReadDependency("course", str(context.course_id), version)
        return (item, item) if self.duplicate else (item,)


class FlexibleDependencies:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self, *, context: ExecutionContext, inputs: JsonObject
    ) -> tuple[ReadDependency, ...]:
        self.calls += 1
        assert context.course_id
        assert inputs
        return (ReadDependency("course", str(context.course_id), "sequence-1"),)


class FlexibleAnswerTool:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture.answer"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls += 1
        assert "clarification" in arguments
        return {"answer": "Recorded."}


class StaticAnswerTool:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture.answer"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls += 1
        assert arguments == {}
        return {"answer": "Draft."}


class TerminatingValidator:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def id(self) -> str:
        return "fixture.stop"

    @property
    def version(self) -> SemanticVersion:
        return V1

    async def validate(self, inputs: JsonObject) -> ValidationOutcome:
        self.calls += 1
        assert inputs == {"draft": {"answer": "Draft."}}
        return ValidationOutcome(
            True,
            ValidatorDisposition.TERMINATE,
            {"answer": "Stopped safely."},
            "fixture requested a safe stop",
        )


class FailingModel(UnusedModel):
    def __init__(self, error: ModelError) -> None:
        self.error = error
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        self.calls += 1
        raise self.error


def _definition() -> PlaybookDefinition:
    clarification = DataReference(DataSourceKind.STEP_OUTPUT, "clarification")
    return PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                "clarify",
                "What aspect should we focus on?",
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
                "answer",
                ArtifactReference("fixture.answer", V1),
                {},
                "answer",
                (DataBinding("clarification", clarification),),
            ),
        ),
        ("topic",),
    )


def _manifest(*, authority: tuple[str, ...] = ("study:explain",)) -> CapabilityManifest:
    return CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        authority,
        True,
    )


def _skill(definition: PlaybookDefinition) -> SkillPackage:
    return SkillPackage(
        "explain_concept",
        V1,
        "Explain a learner-selected concept.",
        VersionRange(V1, V2),
        JsonSchema(INPUT_SCHEMA),
        JsonSchema(OUTPUT_SCHEMA),
        (
            PromptLayer(
                "policy", V1, PromptLayerKind.STUDY_SECURITY_POLICY, "Test policy."
            ),
        ),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (ToolRequirement("fixture.answer", V1),),
        ArtifactReference(definition.id, definition.version),
    )


def _pins(skill: SkillPackage, definition: PlaybookDefinition) -> VersionPins:
    return VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(definition.id, definition.version),
        ArtifactReference("explain_prompt", V1),
        (ToolBehaviorPin("fixture.answer", V1),),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )


def _gateway(
    *,
    dependencies: Dependencies | None = None,
    authority: tuple[str, ...] = ("study:explain",),
    store: MemoryRunStore | None = None,
) -> tuple[StudyCapabilityGateway, AnswerTool, Dependencies]:
    definition = _definition()
    manifest = _manifest(authority=authority)
    skill = _skill(definition)
    resolver = dependencies or Dependencies()
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        resolver,
    )
    tool = AnswerTool()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=store or MemoryRunStore(),
        clock=Clock(),
    )
    return StudyCapabilityGateway(bindings=(binding,), engine=engine), tool, resolver


def _schema_gateway(
    *, input_value_schema: JsonObject, response_value_schema: JsonObject
) -> tuple[StudyCapabilityGateway, FlexibleAnswerTool, FlexibleDependencies]:
    input_schema: JsonObject = {
        "type": "object",
        "required": ("topic",),
        "properties": {"topic": input_value_schema},
        "additionalProperties": False,
    }
    response_schema: JsonObject = {
        "type": "object",
        "required": ("value",),
        "properties": {"value": response_value_schema},
        "additionalProperties": False,
    }
    clarification = DataReference(DataSourceKind.STEP_OUTPUT, "clarification")
    definition = PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                "clarify",
                "Provide the requested value.",
                JsonSchema(response_schema),
                "clarification",
            ),
            ToolStep(
                "answer",
                ArtifactReference("fixture.answer", V1),
                {},
                "answer",
                (DataBinding("clarification", clarification),),
            ),
        ),
        ("topic",),
    )
    manifest = CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        input_schema,
        OUTPUT_SCHEMA,
        ("study:explain",),
        True,
    )
    skill = replace(
        _skill(definition),
        input_schema=JsonSchema(input_schema),
    )
    resolver = FlexibleDependencies()
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        resolver,
    )
    tool = FlexibleAnswerTool()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    return StudyCapabilityGateway(bindings=(binding,), engine=engine), tool, resolver


def _model_failure_gateway(
    error: ModelError,
) -> tuple[StudyCapabilityGateway, FailingModel, Dependencies]:
    prompt = ArtifactReference("explain_prompt", V1)
    definition = PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            ModelStep(
                "answer",
                prompt,
                ModelRequest((ModelMessage(MessageRole.USER, "Explain the topic."),)),
                JsonSchema(OUTPUT_SCHEMA),
                "answer",
            ),
        ),
        ("topic",),
    )
    manifest = CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        ("study:explain",),
        False,
    )
    skill = replace(_skill(definition), required_tools=())
    pins = VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(definition.id, definition.version),
        prompt,
        (),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )
    resolver = Dependencies()
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        pins,
        "answer",
        resolver,
    )
    model = FailingModel(error)
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=model,
        registries=RuntimeRegistries(),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    return StudyCapabilityGateway(bindings=(binding,), engine=engine), model, resolver


def _context(
    *,
    principal_kind: PrincipalKind = PrincipalKind.SERVICE,
    principal_id: str = "tutor-host",
    course_id: CourseId = COURSE,
    session_id: SessionId | None = SESSION,
    grants: frozenset[str] = frozenset({"study:explain"}),
    key: str | None = "retry-1",
    correlation: str = "correlation-1",
    model_run: str | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        principal_kind,
        principal_id,
        course_id,
        CorrelationId(correlation),
        grants,
        session_id,
        None if model_run is None else ModelRunId(model_run),
        key,
    )


def test_start_rejects_authority_identity_schema_and_dependencies_before_engine_effects() -> None:
    invalid = (
        (_context(session_id=None), CapabilityGatewayErrorCode.INVALID_REQUEST),
        (_context(key=None), CapabilityGatewayErrorCode.INVALID_REQUEST),
        (
            _context(principal_kind=PrincipalKind.MODEL),
            CapabilityGatewayErrorCode.UNAUTHORIZED,
        ),
        (_context(grants=frozenset()), CapabilityGatewayErrorCode.UNAUTHORIZED),
    )
    for context, code in invalid:
        gateway, tool, resolver = _gateway()
        with pytest.raises(CapabilityGatewayError) as caught:
            asyncio.run(gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, context))
        assert caught.value.code is code
        assert resolver.calls == 0
        assert tool.calls == 0

    for malformed_context in (
        replace(_context(), course_id=cast(CourseId, "not-a-course-id")),
        replace(_context(), session_id=cast(SessionId, "not-a-session-id")),
    ):
        gateway, tool, resolver = _gateway()
        with pytest.raises(TypeError):
            asyncio.run(
                gateway.start(
                    TutorCapabilityId.EXPLAIN_CONCEPT,
                    INPUTS,
                    malformed_context,
                )
            )
        assert resolver.calls == 0
        assert tool.calls == 0

    gateway, tool, resolver = _gateway()
    with pytest.raises(CapabilityGatewayError) as malformed:
        asyncio.run(
            gateway.start(
                TutorCapabilityId.EXPLAIN_CONCEPT,
                {"topic": 7},
                _context(),
            )
        )
    assert malformed.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST
    assert resolver.calls == 0 and tool.calls == 0

    duplicate = Dependencies(duplicate=True)
    gateway, tool, _ = _gateway(dependencies=duplicate)
    with pytest.raises(CapabilityGatewayError) as bad_dependencies:
        asyncio.run(gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context()))
    assert bad_dependencies.value.code is CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME
    assert duplicate.calls == 1 and tool.calls == 0


def test_run_identity_ignores_correlation_and_model_run_but_binds_authority_scope() -> None:
    gateway, _, resolver = _gateway()
    first = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(first, SuspendedCapabilityOutcome)
    same = asyncio.run(
        gateway.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            INPUTS,
            _context(correlation="other", model_run="model-run-2"),
        )
    )
    assert isinstance(same, SuspendedCapabilityOutcome)
    assert same.run_id == first.run_id
    assert resolver.calls == 1

    variants = (
        _context(principal_kind=PrincipalKind.HUMAN),
        _context(principal_id="other-host"),
        _context(course_id=CourseId("other-course")),
        _context(session_id=SessionId("other-session")),
        _context(grants=frozenset({"study:explain", "study:extra"})),
        _context(key="retry-2"),
    )
    identities: list[RunId] = []
    for context in variants:
        isolated, _, _ = _gateway()
        outcome = asyncio.run(
            isolated.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, context)
        )
        assert isinstance(outcome, SuspendedCapabilityOutcome)
        identities.append(outcome.run_id)
    assert first.run_id not in identities
    assert len(set(identities)) == len(identities)

    changed_manifest, _, _ = _gateway(authority=("study:explain", "study:extra"))
    changed = asyncio.run(
        changed_manifest.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            INPUTS,
            _context(grants=frozenset({"study:explain", "study:extra"})),
        )
    )
    assert isinstance(changed, SuspendedCapabilityOutcome)
    assert changed.run_id != first.run_id


def test_start_resume_and_cas_loser_retries_converge_without_repeating_effects() -> None:
    gateway, tool, resolver = _gateway()
    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    assert suspended.dialogue_request == "What aspect should we focus on?"
    assert tool.calls == 0 and resolver.calls == 1

    response: JsonObject = {"text": "focus on cusps"}
    completed = asyncio.run(gateway.resume(suspended.continuation, response, _context()))
    assert isinstance(completed, CompletedCapabilityOutcome)
    assert completed.run.outputs["answer"] == completed.output
    assert tool.calls == 1 and resolver.calls == 2

    exact = asyncio.run(gateway.resume(suspended.continuation, response, _context()))
    assert isinstance(exact, CompletedCapabilityOutcome)
    assert exact.run == completed.run
    assert tool.calls == 1 and resolver.calls == 2

    with pytest.raises(CapabilityGatewayError) as changed:
        asyncio.run(
            gateway.resume(
                suspended.continuation,
                {"text": "different response"},
                _context(),
            )
        )
    assert changed.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert tool.calls == 1

    forged = replace(
        suspended.continuation,
        checkpoint_fingerprint="f" * 64,
    )
    with pytest.raises(CapabilityGatewayError) as replayed:
        asyncio.run(gateway.resume(forged, response, _context()))
    assert replayed.value.code is CapabilityGatewayErrorCode.CONFLICT


def test_resume_token_binds_every_generation_authority_and_runtime_field() -> None:
    gateway, tool, _ = _gateway()
    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    token = suspended.continuation
    variants = (
        replace(token, authority_fingerprint="1" * 64),
        replace(token, retry_identity_fingerprint="2" * 64),
        replace(token, manifest_fingerprint="3" * 64),
        replace(token, definition_fingerprint="4" * 64),
        replace(token, checkpoint_fingerprint="5" * 64),
        replace(token, dialogue_step_id="later_dialogue"),
        replace(token, next_step_index=2),
        replace(token, inputs={"topic": "mitral valve"}),
        replace(
            token,
            pins=replace(
                token.pins,
                state_contract=ArtifactReference("other_state", V1),
            ),
        ),
        replace(
            token,
            read_dependencies=(
                ReadDependency("course", str(COURSE), "sequence-other"),
            ),
        ),
    )
    for forged in variants:
        with pytest.raises(CapabilityGatewayError) as caught:
            asyncio.run(
                gateway.resume(
                    forged,
                    {"text": "focus on cusps"},
                    _context(),
                )
            )
        assert caught.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert tool.calls == 0


def test_dependency_drift_is_the_only_stale_resume_path() -> None:
    dependencies = Dependencies(drift=True)
    gateway, tool, _ = _gateway(dependencies=dependencies)
    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    outcome = asyncio.run(
        gateway.resume(
            suspended.continuation,
            {"text": "focus on cusps"},
            _context(),
        )
    )
    assert isinstance(outcome, StaleCapabilityOutcome)
    assert tool.calls == 0


def test_resume_cas_loser_observes_running_winner_without_effects() -> None:
    store = MemoryRunStore()
    gateway, tool, resolver = _gateway(store=store)
    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    store.converge_on_cas = store.cas_calls + 1
    with pytest.raises(CapabilityGatewayError) as loser:
        asyncio.run(
            gateway.resume(
                suspended.continuation,
                {"text": "focus on cusps"},
                _context(),
            )
        )
    assert loser.value.code is CapabilityGatewayErrorCode.IN_PROGRESS
    assert loser.value.retryable is True
    assert tool.calls == 0
    assert resolver.calls == 2


def test_non_json_payloads_are_invalid_before_new_effects() -> None:
    gateway, tool, resolver = _gateway()
    with pytest.raises(CapabilityGatewayError) as invalid_inputs:
        asyncio.run(
            gateway.start(
                TutorCapabilityId.EXPLAIN_CONCEPT,
                cast(JsonObject, {"topic": object()}),
                _context(),
            )
        )
    assert invalid_inputs.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST
    assert resolver.calls == 0 and tool.calls == 0

    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    assert resolver.calls == 1 and tool.calls == 0

    with pytest.raises(CapabilityGatewayError) as invalid_response:
        asyncio.run(
            gateway.resume(
                suspended.continuation,
                cast(JsonObject, {"text": object()}),
                _context(),
            )
        )
    assert invalid_response.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST
    assert resolver.calls == 1 and tool.calls == 0


def test_engine_derives_resume_generation_from_actual_suspended_checkpoint() -> None:
    assert "resume_generation_fingerprint" not in inspect.signature(
        PlaybookEngine.resume
    ).parameters
    definition = _definition()
    skill = _skill(definition)
    pins = _pins(skill, definition)
    tool = AnswerTool()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    run_id = RunId("direct-resume-generation")
    dependencies = (ReadDependency("course", str(COURSE), "sequence-1"),)
    asyncio.run(
        engine.execute(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs=INPUTS,
            pins=pins,
            read_dependencies=dependencies,
        )
    )
    suspended = engine.inspect(run_id=run_id, definition=definition)
    asyncio.run(
        engine.resume(
            run_id=run_id,
            skill=skill,
            definition=definition,
            inputs=INPUTS,
            pins=pins,
            read_dependencies=dependencies,
            resume_input={"text": "focus on cusps"},
        )
    )
    completed = engine.inspect(run_id=run_id, definition=definition)
    dialogue_receipts = tuple(
        trace.details["resume_generation_fingerprint"]
        for trace in completed.traces
        if trace.step_id == "clarify" and trace.status.value == "completed"
    )
    assert dialogue_receipts == (suspended.checkpoint_fingerprint,)


def test_token_from_prior_dialogue_generation_cannot_resume_later_dialogue() -> None:
    definition = PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                "clarify",
                "What aspect should we focus on?",
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
            DialogueStep(
                "confirm",
                "Do you want a short explanation?",
                JsonSchema(
                    {
                        "type": "object",
                        "required": ("confirmed",),
                        "properties": {"confirmed": {"type": "boolean"}},
                        "additionalProperties": False,
                    }
                ),
                "confirmation",
            ),
            ToolStep(
                "answer",
                ArtifactReference("fixture.answer", V1),
                {},
                "answer",
            ),
        ),
        ("topic",),
    )
    manifest = _manifest()
    skill = _skill(definition)
    resolver = Dependencies()
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        resolver,
    )
    tool = AnswerTool()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    gateway = StudyCapabilityGateway(bindings=(binding,), engine=engine)
    first = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(first, SuspendedCapabilityOutcome)
    second = asyncio.run(
        gateway.resume(
            first.continuation,
            {"text": "focus on cusps"},
            _context(),
        )
    )
    assert isinstance(second, SuspendedCapabilityOutcome)
    assert second.continuation.dialogue_step_id == "confirm"
    with pytest.raises(CapabilityGatewayError) as replay:
        asyncio.run(
            gateway.resume(
                first.continuation,
                {"text": "focus on cusps"},
                _context(),
            )
        )
    assert replay.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert tool.calls == 0


def test_changed_start_input_conflicts_without_restarting() -> None:
    gateway, tool, resolver = _gateway()
    first = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(first, SuspendedCapabilityOutcome)
    with pytest.raises(CapabilityGatewayError) as changed:
        asyncio.run(
            gateway.start(
                TutorCapabilityId.EXPLAIN_CONCEPT,
                {"topic": "mitral valve"},
                _context(),
            )
        )
    assert changed.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert resolver.calls == 1 and tool.calls == 0


@pytest.mark.parametrize(
    ("first", "changed"),
    ((1, 1.0),),
)
def test_start_retry_uses_exact_json_scalar_identity(
    first: int | float | bool, changed: int | float | bool
) -> None:
    gateway, tool, resolver = _schema_gateway(
        input_value_schema={"type": "number"},
        response_value_schema={"type": "number"},
    )
    suspended = asyncio.run(
        gateway.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            {"topic": first},
            _context(),
        )
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    with pytest.raises(CapabilityGatewayError) as mismatch:
        asyncio.run(
            gateway.start(
                TutorCapabilityId.EXPLAIN_CONCEPT,
                {"topic": changed},
                _context(),
            )
        )
    assert mismatch.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert resolver.calls == 1 and tool.calls == 0


@pytest.mark.parametrize(
    ("first", "changed"),
    ((1, 1.0),),
)
def test_resume_retry_uses_exact_json_scalar_identity(
    first: int | float | bool, changed: int | float | bool
) -> None:
    gateway, tool, resolver = _schema_gateway(
        input_value_schema={"type": "string"},
        response_value_schema={"type": "number"},
    )
    suspended = asyncio.run(
        gateway.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            {"topic": "aortic valve"},
            _context(),
        )
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)
    completed = asyncio.run(
        gateway.resume(suspended.continuation, {"value": first}, _context())
    )
    assert isinstance(completed, CompletedCapabilityOutcome)
    with pytest.raises(CapabilityGatewayError) as mismatch:
        asyncio.run(
            gateway.resume(
                suspended.continuation,
                {"value": changed},
                _context(),
            )
        )
    assert mismatch.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert resolver.calls == 2 and tool.calls == 1


def test_invalid_dialogue_response_preserves_suspension_for_valid_retry() -> None:
    gateway, tool, resolver = _gateway()
    suspended = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(suspended, SuspendedCapabilityOutcome)

    with pytest.raises(CapabilityGatewayError) as invalid:
        asyncio.run(
            gateway.resume(
                suspended.continuation,
                {"text": 7},
                _context(),
            )
        )
    assert invalid.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST
    assert resolver.calls == 1 and tool.calls == 0

    completed = asyncio.run(
        gateway.resume(
            suspended.continuation,
            {"text": "focus on cusps"},
            _context(),
        )
    )
    assert isinstance(completed, CompletedCapabilityOutcome)
    assert resolver.calls == 2 and tool.calls == 1


def test_raw_string_principal_kind_is_rejected_before_effects() -> None:
    gateway, tool, resolver = _gateway()
    raw_context = replace(
        _context(), principal_kind=cast(PrincipalKind, PrincipalKind.SERVICE.value)
    )
    with pytest.raises(TypeError, match="principal_kind"):
        asyncio.run(
            gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, raw_context)
        )
    assert resolver.calls == 0 and tool.calls == 0


def test_real_engine_terminal_outcomes_expose_proof_only_for_termination() -> None:
    definition = PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            ToolStep(
                "draft",
                ArtifactReference("fixture.answer", V1),
                {},
                "draft",
            ),
            ValidateStep(
                "stop",
                ArtifactReference("fixture.stop", V1),
                ("draft",),
                "answer",
            ),
        ),
        ("topic",),
    )
    manifest = CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        ("study:explain",),
        False,
    )
    skill = replace(
        _skill(definition),
        validators=(ValidatorDefinition("fixture.stop", V1, "Stop safely."),),
    )
    resolver = Dependencies()
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        resolver,
    )
    tool = StaticAnswerTool()
    validator = TerminatingValidator()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,), (validator,)),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    gateway = StudyCapabilityGateway(bindings=(binding,), engine=engine)
    terminated = asyncio.run(
        gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
    )
    assert isinstance(terminated, TerminatedCapabilityOutcome)
    assert terminated.run.status is PlaybookRunStatus.TERMINATED
    assert not hasattr(terminated, "output")
    assert tool.calls == 1 and validator.calls == 1 and resolver.calls == 1

    cancelled_gateway, cancelled_model, cancelled_dependencies = (
        _model_failure_gateway(
            ModelError(ModelErrorCode.CANCELLED, "transport confirmed cancellation")
        )
    )
    cancelled = asyncio.run(
        cancelled_gateway.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            INPUTS,
            _context(key="cancelled"),
        )
    )
    assert isinstance(cancelled, CancelledCapabilityOutcome)
    assert not hasattr(cancelled, "run") and not hasattr(cancelled, "output")
    assert cancelled_model.calls == 1 and cancelled_dependencies.calls == 1

    failed_gateway, failed_model, failed_dependencies = _model_failure_gateway(
        ModelError(ModelErrorCode.TIMEOUT, "fixture timeout", retryable=True)
    )
    failed = asyncio.run(
        failed_gateway.start(
            TutorCapabilityId.EXPLAIN_CONCEPT,
            INPUTS,
            _context(key="failed"),
        )
    )
    assert isinstance(failed, FailedCapabilityOutcome)
    assert not hasattr(failed, "run") and not hasattr(failed, "output")
    assert failed_model.calls == 1 and failed_dependencies.calls == 1


def test_ambiguous_running_retry_is_retryable_in_progress_without_reexecution() -> None:
    definition = PlaybookDefinition(
        "explain_concept_flow",
        V1,
        VersionRange(V1, V2),
        (
            ToolStep(
                "answer",
                ArtifactReference("fixture.answer", V1),
                {},
                "answer",
            ),
        ),
        ("topic",),
    )
    manifest = CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        ("study:explain",),
        False,
    )
    skill = _skill(definition)
    dependencies = Dependencies()

    class InterruptedTool:
        def __init__(self) -> None:
            self.calls = 0

        @property
        def name(self) -> str:
            return "fixture.answer"

        @property
        def behavior_version(self) -> SemanticVersion:
            return V1

        async def invoke(self, arguments: JsonObject) -> JsonObject:
            assert arguments == {}
            self.calls += 1
            raise asyncio.CancelledError

    tool = InterruptedTool()
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=MemoryRunStore(),
        clock=Clock(),
    )
    binding = CapabilityBinding(
        manifest,
        manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        dependencies,
    )
    gateway = StudyCapabilityGateway(bindings=(binding,), engine=engine)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
        )
    with pytest.raises(CapabilityGatewayError) as caught:
        asyncio.run(
            gateway.start(TutorCapabilityId.EXPLAIN_CONCEPT, INPUTS, _context())
        )
    assert caught.value.code is CapabilityGatewayErrorCode.IN_PROGRESS
    assert caught.value.retryable is True
    assert tool.calls == 1
