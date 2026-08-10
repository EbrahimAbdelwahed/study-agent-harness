from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from study_agent.api import capabilities as capability_api
from study_agent.api.authority import HostAuthority
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
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
    ReadDependency,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolStep,
    VersionPins,
)
from study_agent.ports import (
    CancellationToken,
    MessageRole,
    ModelCapabilities,
    ModelError,
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
    VersionRange,
)

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
COURSE = CourseId("pf06-course")
SESSION = SessionId("pf06-session")
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
RESPONSE_SCHEMA: JsonObject = {
    "type": "object",
    "required": ("text",),
    "properties": {"text": {"type": "string"}},
    "additionalProperties": False,
}


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 10, 12, tzinfo=UTC)


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


class RecordingTool:
    name = "fixture.answer"
    behavior_version = V1

    def __init__(self, output: JsonObject | None = None, error: Exception | None = None) -> None:
        self.calls = 0
        self.arguments: list[JsonObject] = []
        self.output = output or {"answer": "Three cusps."}
        self.error = error

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls += 1
        self.arguments.append(arguments)
        if self.error is not None:
            raise self.error
        return self.output


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


class FailingModel(UnusedModel):
    def __init__(self, error: ModelError) -> None:
        self.error = error
        self.calls = 0

    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        self.calls += 1
        raise self.error


class Dependencies:
    def __init__(self, *, drift_after_first: bool = False) -> None:
        self.calls = 0
        self.drift_after_first = drift_after_first

    def __call__(
        self, *, context: ExecutionContext, inputs: JsonObject
    ) -> tuple[ReadDependency, ...]:
        del inputs
        self.calls += 1
        version = (
            "sequence-2"
            if self.drift_after_first and self.calls > 1
            else "sequence-1"
        )
        return (ReadDependency("course", str(context.course_id), version),)


@dataclass(frozen=True)
class GatewayFixture:
    gateway: capability_api.StudyCapabilityGateway
    tool: RecordingTool
    dependencies: Dependencies
    store: MemoryRunStore
    binding: capability_api.CapabilityBinding
    authority: HostAuthority


def manifest(
    *,
    authority: tuple[str, ...] = ("study:explain",),
    supports_suspension: bool = False,
) -> capability_api.CapabilityManifest:
    return capability_api.CapabilityManifest(
        capability_api.TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        authority,
        supports_suspension,
        V1,
    )


def _definition(*, supports_suspension: bool) -> PlaybookDefinition:
    steps: tuple[DialogueStep | ToolStep, ...]
    if supports_suspension:
        steps = (
            DialogueStep(
                "clarify",
                "What should we focus on?",
                JsonSchema(RESPONSE_SCHEMA),
                "clarification",
            ),
            ToolStep(
                "answer",
                ArtifactReference("fixture.answer", V1),
                {},
                "answer",
                (
                    DataBinding(
                        "clarification",
                        DataReference(DataSourceKind.STEP_OUTPUT, "clarification"),
                    ),
                ),
            ),
        )
    else:
        steps = (ToolStep("answer", ArtifactReference("fixture.answer", V1), {}, "answer"),)
    return PlaybookDefinition(
        "pf06-explain-flow",
        V1,
        VersionRange(V1, V2),
        steps,
        ("topic",),
    )


def _skill(definition: PlaybookDefinition) -> SkillPackage:
    return SkillPackage(
        "explain_concept",
        V1,
        "Explain one learner-selected concept.",
        VersionRange(V1, V2),
        JsonSchema(INPUT_SCHEMA),
        JsonSchema(OUTPUT_SCHEMA),
        (PromptLayer("policy", V1, PromptLayerKind.STUDY_SECURITY_POLICY, "Test policy."),),
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
        ArtifactReference("pf06-prompt", V1),
        (ToolBehaviorPin("fixture.answer", V1),),
        ArtifactReference("pf06-model", V1),
        ArtifactReference("pf06-state", V1),
    )


def build_gateway(
    *,
    supports_suspension: bool = False,
    authority: tuple[str, ...] = ("study:explain",),
    tool_output: JsonObject | None = None,
    tool_error: Exception | None = None,
    dependencies: Dependencies | None = None,
    store: MemoryRunStore | None = None,
) -> GatewayFixture:
    definition = _definition(supports_suspension=supports_suspension)
    skill = _skill(definition)
    selected_dependencies = dependencies or Dependencies()
    selected_store = store or MemoryRunStore()
    host_authority = HostAuthority()
    selected_manifest = manifest(
        authority=authority,
        supports_suspension=supports_suspension,
    )
    binding = capability_api.CapabilityBinding(
        selected_manifest,
        selected_manifest.fingerprint,
        skill,
        definition,
        _pins(skill, definition),
        "answer",
        selected_dependencies,
    )
    tool = RecordingTool(output=tool_output, error=tool_error)
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("pf06-model", V1),
        state_contract=ArtifactReference("pf06-state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=selected_store,
        clock=FixedClock(),
    )
    return GatewayFixture(
        capability_api.StudyCapabilityGateway(bindings=(binding,), engine=engine),
        tool,
        selected_dependencies,
        selected_store,
        binding,
        host_authority,
    )


def context(
    *,
    principal_kind: PrincipalKind = PrincipalKind.SERVICE,
    principal_id: str = "pf06-host",
    grants: frozenset[str] = frozenset({"study:explain"}),
    key: str | None = "pf06-retry",
    correlation: str = "pf06-correlation",
) -> ExecutionContext:
    return ExecutionContext(
        principal_kind,
        principal_id,
        COURSE,
        CorrelationId(correlation),
        grants,
        SESSION,
        None,
        key,
    )


def build_model_failure_gateway(
    error: ModelError,
) -> tuple[capability_api.StudyCapabilityGateway, FailingModel]:
    definition = PlaybookDefinition(
        "pf06-model-flow",
        V1,
        VersionRange(V1, V2),
        (
            ModelStep(
                "answer",
                ArtifactReference("pf06-prompt", V1),
                ModelRequest((ModelMessage(MessageRole.USER, "Explain the topic."),)),
                JsonSchema(OUTPUT_SCHEMA),
                "answer",
            ),
        ),
        ("topic",),
    )
    skill = SkillPackage(
        "explain_concept",
        V1,
        "Explain one learner-selected concept.",
        VersionRange(V1, V2),
        JsonSchema(INPUT_SCHEMA),
        JsonSchema(OUTPUT_SCHEMA),
        (PromptLayer("policy", V1, PromptLayerKind.STUDY_SECURITY_POLICY, "Test policy."),),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (),
        ArtifactReference(definition.id, definition.version),
    )
    selected_manifest = manifest()
    pins = VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(definition.id, definition.version),
        ArtifactReference("pf06-prompt", V1),
        (),
        ArtifactReference("pf06-model", V1),
        ArtifactReference("pf06-state", V1),
    )
    dependencies = Dependencies()
    binding = capability_api.CapabilityBinding(
        selected_manifest,
        selected_manifest.fingerprint,
        skill,
        definition,
        pins,
        "answer",
        dependencies,
    )
    model = FailingModel(error)
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("pf06-model", V1),
        state_contract=ArtifactReference("pf06-state", V1),
        model=model,
        registries=RuntimeRegistries(),
        run_store=MemoryRunStore(),
        clock=FixedClock(),
    )
    return capability_api.StudyCapabilityGateway(bindings=(binding,), engine=engine), model
