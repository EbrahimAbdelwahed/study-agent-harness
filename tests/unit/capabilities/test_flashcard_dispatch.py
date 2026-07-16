from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from study_agent.artifacts.candidates import (
    FlashcardAnswerBlock,
    FlashcardCandidate,
    FlashcardCandidateBatch,
    FlashcardPedagogicalRole,
)
from study_agent.capabilities import (
    PROFILE_SELECTION_RECEIPT_INPUT,
    PROPOSE_FLASHCARDS_MANIFEST,
    CapabilityBinding,
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    FlashcardCapabilityDispatcher,
    ProfiledCapabilityBinding,
    StudyCapabilityGateway,
    SuspendedCapabilityOutcome,
)
from study_agent.capabilities.worker_adapter import ProfiledWorkerExecutionDescriptor
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    InteractionId,
    PrincipalKind,
    RetrievalForm,
    RevisionId,
    RunId,
    SessionId,
)
from study_agent.domain._validation import JsonObject
from study_agent.pedagogy import (
    HYBRID_MACRO_DETAIL_V1,
    MORPHOLOGY_FIRST_ANATOMY_V1,
    PedagogicalProfileRef,
    ProfileSelectionBasis,
    ProfileSelectionMode,
    ProfileSelectionReceipt,
    ProfileSelectorKind,
)
from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueStep,
    PlaybookDefinition,
    PlaybookEngine,
    RuntimeRegistries,
    ToolBehaviorPin,
    ToolStep,
    ValidateStep,
    VersionPins,
    playbook_definition_fingerprint,
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
    CapabilityFallback,
    CapabilityRequirement,
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
from study_agent.skills.builtin import (
    PROPOSE_FLASHCARDS_INPUT_SCHEMA,
    PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
)
from study_agent.workers import (
    GenerationWorkerTask,
    GenerationWorkerTaskKind,
    ValidationExpectation,
    ValidationReceiptSource,
    fingerprint_output_schema,
)

V1 = SemanticVersion.parse("1.0.0")
V2 = SemanticVersion.parse("2.0.0")
PUBLIC_INPUTS: JsonObject = {
    "query": "Prepare cards on the aortic root.",
    "scope": None,
    "language": "en",
    "candidate_ceiling": 8,
    "continuation_summary_json": None,
}
RESPONSE: JsonObject = {"confirmed": True}


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 15, 12, tzinfo=UTC)


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


class CandidateTool:
    def __init__(self, output: JsonObject) -> None:
        self.output = output
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixture.cards"

    @property
    def behavior_version(self) -> SemanticVersion:
        return V1

    async def invoke(self, arguments: JsonObject) -> JsonObject:
        self.calls += 1
        assert arguments == {"confirmed": {"confirmed": True}}
        return self.output


def _batch() -> FlashcardCandidateBatch:
    return FlashcardCandidateBatch(
        (
            FlashcardCandidate(
                "overview",
                None,
                RetrievalForm.DIRECT_RECALL,
                "What organizes the aortic root?",
                (FlashcardAnswerBlock("Framework", "Three levels.", ("annulus",)),),
                FlashcardPedagogicalRole.OVERVIEW,
                None,
                None,
                "A framework card is earned.",
                ("evidence-1",),
                (),
            ),
        ),
        (),
    )


def _definition(profile: PedagogicalProfileRef) -> PlaybookDefinition:
    confirmation = DataReference(DataSourceKind.STEP_OUTPUT, "confirmation")
    suffix = "hybrid" if profile == HYBRID_MACRO_DETAIL_V1 else "morphology"
    return PlaybookDefinition(
        f"propose_flashcards_{suffix}_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                f"confirm_{suffix}",
                f"Confirm the {suffix} proposal boundary.",
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
                f"emit_{suffix}",
                ArtifactReference("fixture.cards", V1),
                {},
                "candidates",
                (DataBinding("confirmed", confirmation),),
            ),
        ),
        (*PUBLIC_INPUTS, PROFILE_SELECTION_RECEIPT_INPUT),
    )


def _skill(profile: PedagogicalProfileRef, definition: PlaybookDefinition) -> SkillPackage:
    suffix = "hybrid" if profile == HYBRID_MACRO_DETAIL_V1 else "morphology"
    return SkillPackage(
        f"propose_flashcards_{suffix}",
        V1,
        f"Propose grounded {suffix} flashcards.",
        VersionRange(V1, V2),
        PROPOSE_FLASHCARDS_INPUT_SCHEMA,
        PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
        (
            PromptLayer(
                f"{suffix}_task",
                V1,
                PromptLayerKind.TASK_INSTRUCTION,
                f"Apply the closed {suffix} profile.",
            ),
        ),
        (),
        GroundingPolicy(True, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (ToolRequirement("fixture.cards", V1),),
        ArtifactReference(definition.id, definition.version),
    )


def _profiled_binding(profile: PedagogicalProfileRef) -> ProfiledCapabilityBinding:
    definition = _definition(profile)
    skill = _skill(profile, definition)
    suffix = "hybrid" if profile == HYBRID_MACRO_DETAIL_V1 else "morphology"
    pins = VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(definition.id, definition.version),
        ArtifactReference(f"{suffix}_prompt", V1),
        (ToolBehaviorPin("fixture.cards", V1),),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )
    return ProfiledCapabilityBinding(
        PROPOSE_FLASHCARDS_MANIFEST,
        PROPOSE_FLASHCARDS_MANIFEST.fingerprint,
        profile,
        skill,
        definition,
        pins,
        "candidates",
        lambda *, context, inputs: (),
    )


def _ordinary_binding() -> CapabilityBinding:
    from study_agent.capabilities import EXPLAIN_CONCEPT_MANIFEST

    input_properties = EXPLAIN_CONCEPT_MANIFEST.input_schema["properties"]
    assert isinstance(input_properties, Mapping)
    definition = PlaybookDefinition(
        "fixture_ordinary_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                "clarify",
                "Clarify the ordinary request.",
                JsonSchema(
                    {
                        "type": "object",
                        "required": ("confirmed",),
                        "properties": {"confirmed": {"type": "boolean"}},
                        "additionalProperties": False,
                    }
                ),
                "clarification",
            ),
            ToolStep("answer", ArtifactReference("fixture.cards", V1), {}, "answer"),
        ),
        tuple(input_properties),
    )
    skill = SkillPackage(
        "explain_concept",
        V1,
        "Fixture ordinary capability.",
        VersionRange(V1, V2),
        JsonSchema(EXPLAIN_CONCEPT_MANIFEST.input_schema),
        JsonSchema(EXPLAIN_CONCEPT_MANIFEST.output_schema),
        (PromptLayer("task", V1, PromptLayerKind.TASK_INSTRUCTION, "Fixture."),),
        (),
        GroundingPolicy(False, "insufficient_evidence"),
        StateWritePolicy(),
        (),
        (ToolRequirement("fixture.cards", V1),),
        ArtifactReference(definition.id, V1),
    )
    pins = VersionPins(
        ArtifactReference(skill.id, V1),
        ArtifactReference(definition.id, V1),
        ArtifactReference("ordinary_prompt", V1),
        (ToolBehaviorPin("fixture.cards", V1),),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )
    return CapabilityBinding(
        EXPLAIN_CONCEPT_MANIFEST,
        EXPLAIN_CONCEPT_MANIFEST.fingerprint,
        skill,
        definition,
        pins,
        "answer",
        lambda *, context, inputs: (),
    )


def _dispatcher(
    *, output: JsonObject | None = None, store: MemoryRunStore | None = None
) -> tuple[
    FlashcardCapabilityDispatcher,
    CandidateTool,
    tuple[ProfiledCapabilityBinding, ProfiledCapabilityBinding],
    MemoryRunStore,
]:
    selected_store = store or MemoryRunStore()
    tool = CandidateTool(output or _batch().to_json())
    engine = PlaybookEngine(
        engine_version=V1,
        model_adapter=ArtifactReference("fixture_model", V1),
        state_contract=ArtifactReference("event_state", V1),
        model=UnusedModel(),
        registries=RuntimeRegistries((tool,)),
        run_store=selected_store,
        clock=Clock(),
    )
    gateway = StudyCapabilityGateway(bindings=(_ordinary_binding(),), engine=engine)
    bindings = (
        _profiled_binding(HYBRID_MACRO_DETAIL_V1),
        _profiled_binding(MORPHOLOGY_FIRST_ANATOMY_V1),
    )
    return (
        FlashcardCapabilityDispatcher(bindings=bindings, gateway=gateway),
        tool,
        bindings,
        selected_store,
    )


def _context(
    *, kind: PrincipalKind = PrincipalKind.HUMAN, key: str = "request-1"
) -> ExecutionContext:
    return ExecutionContext(
        kind,
        "learner-1",
        CourseId("course-1"),
        CorrelationId("correlation-1"),
        frozenset({"course:read"}),
        SessionId("session-1"),
        None,
        key,
    )


def _explicit(profile: PedagogicalProfileRef) -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        profile,
        ProfileSelectionMode.EXPLICIT_REQUEST,
        ProfileSelectorKind.HUMAN,
        PrincipalKind.HUMAN,
        ProfileSelectionBasis(interaction_id=InteractionId("interaction-1")),
    )


def _trusted(profile: PedagogicalProfileRef) -> ProfileSelectionReceipt:
    return ProfileSelectionReceipt(
        profile,
        ProfileSelectionMode.TRUSTED_METADATA,
        ProfileSelectorKind.TRUSTED_MATERIAL,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(source_revision_id=RevisionId("revision-1")),
    )


def _persisted_receipt(continuation: CapabilityContinuation) -> ProfileSelectionReceipt:
    value = continuation.inputs[PROFILE_SELECTION_RECEIPT_INPUT]
    assert isinstance(value, str)
    return ProfileSelectionReceipt.from_bytes(value.encode())


def test_dispatcher_discovers_one_public_manifest_and_routes_default_and_explicit() -> None:
    dispatcher, _, _, _ = _dispatcher()
    assert dispatcher.discover() == (PROPOSE_FLASHCARDS_MANIFEST,)

    default = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context()))
    explicit = asyncio.run(
        dispatcher.start(
            PUBLIC_INPUTS,
            _context(key="request-2"),
            _explicit(MORPHOLOGY_FIRST_ANATOMY_V1),
        )
    )
    assert isinstance(default, SuspendedCapabilityOutcome)
    assert isinstance(explicit, SuspendedCapabilityOutcome)
    assert default.continuation.pins.skill.id == "propose_flashcards_hybrid"
    assert explicit.continuation.pins.skill.id == "propose_flashcards_morphology"

    persisted = _persisted_receipt(default.continuation)
    assert persisted.profile == HYBRID_MACRO_DETAIL_V1
    assert persisted.mode is ProfileSelectionMode.DEFAULT
    assert persisted.selector_authority is PrincipalKind.HUMAN


def test_default_receipt_uses_exact_executing_service_authority() -> None:
    dispatcher, _, _, _ = _dispatcher()
    outcome = asyncio.run(
        dispatcher.start(PUBLIC_INPUTS, _context(kind=PrincipalKind.SERVICE))
    )
    assert isinstance(outcome, SuspendedCapabilityOutcome)
    receipt = _persisted_receipt(outcome.continuation)
    assert receipt.selector_authority is PrincipalKind.SERVICE


def test_exact_retry_reuses_run_and_changed_receipt_conflicts() -> None:
    dispatcher, tool, _, _ = _dispatcher()
    first = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context()))
    second = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context()))
    assert isinstance(first, SuspendedCapabilityOutcome)
    assert isinstance(second, SuspendedCapabilityOutcome)
    assert second.run_id == first.run_id
    assert tool.calls == 0

    with pytest.raises(CapabilityGatewayError) as raised:
        asyncio.run(
            dispatcher.start(
                PUBLIC_INPUTS,
                _context(),
                _explicit(MORPHOLOGY_FIRST_ANATOMY_V1),
            )
        )
    assert raised.value.code is CapabilityGatewayErrorCode.CONFLICT
    assert tool.calls == 0


def test_resume_uses_checkpoint_receipt_and_completed_output_passes_strict_codec() -> None:
    dispatcher, tool, _, _ = _dispatcher()
    started = asyncio.run(
        dispatcher.start(
            PUBLIC_INPUTS,
            _context(),
            _explicit(MORPHOLOGY_FIRST_ANATOMY_V1),
        )
    )
    assert isinstance(started, SuspendedCapabilityOutcome)

    resumed = asyncio.run(dispatcher.resume(started.continuation, RESPONSE, _context()))
    assert isinstance(resumed, CompletedCapabilityOutcome)
    assert resumed.output == _batch().to_json()
    assert tool.calls == 1


def test_schema_valid_but_codec_invalid_output_fails_closed() -> None:
    invalid = _batch().to_json()
    raw_candidates = invalid["candidates"]
    assert isinstance(raw_candidates, tuple)
    invalid_candidate = dict(cast(Mapping[str, object], raw_candidates[0]))
    invalid_candidate["evidence_ids"] = ("evidence-1", "evidence-1")
    output: JsonObject = {
        "candidates": (cast(JsonObject, invalid_candidate),),
        "omissions": (),
    }
    dispatcher, tool, _, _ = _dispatcher(output=output)
    started = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context()))
    assert isinstance(started, SuspendedCapabilityOutcome)

    resumed = asyncio.run(dispatcher.resume(started.continuation, RESPONSE, _context()))
    assert isinstance(resumed, FailedCapabilityOutcome)
    assert tool.calls == 1


def test_process_loss_recovery_uses_same_profile_without_effect_owner_duplication() -> None:
    dispatcher, _, _, store = _dispatcher()
    started = asyncio.run(
        dispatcher.start(
            PUBLIC_INPUTS,
            _context(),
            _trusted(MORPHOLOGY_FIRST_ANATOMY_V1),
        )
    )
    assert isinstance(started, SuspendedCapabilityOutcome)

    recovered, tool, _, _ = _dispatcher(store=store)
    outcome = asyncio.run(recovered.resume(started.continuation, RESPONSE, _context()))
    assert isinstance(outcome, CompletedCapabilityOutcome)
    assert tool.calls == 1


@pytest.mark.parametrize(
    "changed",
    (
        _explicit(MORPHOLOGY_FIRST_ANATOMY_V1),
        ProfileSelectionReceipt(
            HYBRID_MACRO_DETAIL_V1,
            ProfileSelectionMode.EXPLICIT_REQUEST,
            ProfileSelectorKind.HUMAN,
            PrincipalKind.HUMAN,
            ProfileSelectionBasis(interaction_id=InteractionId("interaction-2")),
        ),
        _trusted(HYBRID_MACRO_DETAIL_V1),
    ),
)
def test_same_retry_with_changed_selection_dimension_conflicts(
    changed: ProfileSelectionReceipt,
) -> None:
    dispatcher, tool, _, _ = _dispatcher()
    original = _explicit(HYBRID_MACRO_DETAIL_V1)
    started = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context(), original))
    assert isinstance(started, SuspendedCapabilityOutcome)
    with pytest.raises(CapabilityGatewayError):
        asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context(), changed))
    assert tool.calls == 0


def test_resume_rejects_tampered_receipt_pins_definition_authority_and_generation() -> None:
    dispatcher, _, _, _ = _dispatcher()
    started = asyncio.run(dispatcher.start(PUBLIC_INPUTS, _context()))
    assert isinstance(started, SuspendedCapabilityOutcome)
    continuation = started.continuation
    tampered = (
        replace(
            continuation,
            inputs={**continuation.inputs, PROFILE_SELECTION_RECEIPT_INPUT: "{}"},
        ),
        replace(
            continuation,
            pins=replace(
                continuation.pins,
                prompt=ArtifactReference("tampered_prompt", V1),
            ),
        ),
        replace(continuation, definition_fingerprint="0" * 64),
        replace(continuation, authority_fingerprint="0" * 64),
        replace(continuation, checkpoint_fingerprint="0" * 64),
    )
    for value in tampered:
        with pytest.raises(CapabilityGatewayError) as raised:
            asyncio.run(dispatcher.resume(value, RESPONSE, _context()))
        assert raised.value.code in {
            CapabilityGatewayErrorCode.CONFLICT,
            CapabilityGatewayErrorCode.INCOMPATIBLE_RUNTIME,
        }


def test_dispatcher_rejects_duplicate_internal_identity_or_definition() -> None:
    dispatcher, _, bindings, _ = _dispatcher()
    duplicate_skill = replace(bindings[1].skill, id=bindings[0].skill.id)
    duplicate_pins = replace(
        bindings[1].pins,
        skill=ArtifactReference(duplicate_skill.id, duplicate_skill.version),
    )
    duplicate_binding = replace(
        bindings[1], skill=duplicate_skill, pins=duplicate_pins
    )
    with pytest.raises(ValueError):
        FlashcardCapabilityDispatcher(
            bindings=(bindings[0], duplicate_binding), gateway=dispatcher._gateway
        )

    duplicate_definition_skill = replace(
        bindings[1].skill,
        playbook=ArtifactReference(
            bindings[0].playbook.id, bindings[0].playbook.version
        ),
    )
    duplicate_definition_pins = replace(
        bindings[1].pins,
        playbook=ArtifactReference(
            bindings[0].playbook.id, bindings[0].playbook.version
        ),
    )
    duplicate_definition = replace(
        bindings[1],
        skill=duplicate_definition_skill,
        playbook=bindings[0].playbook,
        pins=duplicate_definition_pins,
    )
    with pytest.raises(ValueError):
        FlashcardCapabilityDispatcher(
            bindings=(bindings[0], duplicate_definition), gateway=dispatcher._gateway
        )


def test_course_title_or_output_cannot_select_profile() -> None:
    dispatcher, _, _, _ = _dispatcher()
    for extra in ("course_title", "model_profile"):
        with pytest.raises(CapabilityGatewayError) as raised:
            asyncio.run(dispatcher.start({**PUBLIC_INPUTS, extra: "anatomy"}, _context()))
        assert raised.value.code is CapabilityGatewayErrorCode.INVALID_REQUEST


@pytest.mark.parametrize(
    "context",
    (
        _context(kind=PrincipalKind.MODEL),
        replace(_context(), requested_capabilities=frozenset()),
    ),
)
def test_untrusted_or_ungranted_start_fails_before_checkpoint_or_effect(
    context: ExecutionContext,
) -> None:
    dispatcher, tool, _, store = _dispatcher()
    with pytest.raises(CapabilityGatewayError) as raised:
        asyncio.run(dispatcher.start(PUBLIC_INPUTS, context))
    assert raised.value.code is CapabilityGatewayErrorCode.UNAUTHORIZED
    assert store.data == {}
    assert tool.calls == 0


def test_profiled_binding_rejects_state_writes_public_identity_and_missing_receipt() -> None:
    binding = _profiled_binding(HYBRID_MACRO_DETAIL_V1)
    writing_skill = replace(
        binding.skill,
        state_write_policy=StateWritePolicy(("artifact.generated",)),
    )
    with pytest.raises(ValueError, match="state writes"):
        replace(binding, skill=writing_skill)

    public_skill = replace(binding.skill, id="propose_flashcards")
    public_pins = replace(
        binding.pins,
        skill=ArtifactReference(public_skill.id, public_skill.version),
    )
    with pytest.raises(ValueError, match="internal"):
        replace(binding, skill=public_skill, pins=public_pins)

    missing_receipt = replace(binding.playbook, input_keys=tuple(PUBLIC_INPUTS))
    with pytest.raises(ValueError, match="reserved receipt"):
        replace(binding, playbook=missing_receipt)


def test_profiled_binding_forbids_effects_from_reading_selection_receipt() -> None:
    binding = _profiled_binding(HYBRID_MACRO_DETAIL_V1)
    final = binding.playbook.steps[-1]
    assert isinstance(final, ToolStep)
    receipt_binding = DataBinding(
        "selection",
        DataReference(DataSourceKind.RUN_INPUT, PROFILE_SELECTION_RECEIPT_INPUT),
    )
    changed = replace(
        binding.playbook,
        steps=(binding.playbook.steps[0], replace(final, bindings=(receipt_binding,))),
    )
    with pytest.raises(ValueError, match="cannot read"):
        replace(binding, playbook=changed)


def test_profiled_binding_accepts_fallback_only_validator_union_with_explicit_steps() -> None:
    profile = HYBRID_MACRO_DETAIL_V1
    definition = PlaybookDefinition(
        "propose_flashcards_validator_union_flow",
        V1,
        VersionRange(V1, V2),
        (
            DialogueStep(
                "clarify",
                "Confirm generation.",
                JsonSchema(
                    {
                        "type": "object",
                        "required": ("confirmed",),
                        "properties": {"confirmed": {"type": "boolean"}},
                        "additionalProperties": False,
                    }
                ),
                "clarification",
            ),
            ValidateStep(
                "validate_candidates",
                ArtifactReference("explicit_validator", V1),
                ("clarification",),
                "candidates",
            ),
        ),
        (*PUBLIC_INPUTS, PROFILE_SELECTION_RECEIPT_INPUT),
    )
    skill = SkillPackage(
        "propose_flashcards_validator_union",
        V1,
        "Pin fallback-only and explicit validators without conflating their roles.",
        VersionRange(V1, V2),
        PROPOSE_FLASHCARDS_INPUT_SCHEMA,
        PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
        (PromptLayer("task", V1, PromptLayerKind.TASK_INSTRUCTION, "Fixture."),),
        (),
        GroundingPolicy(True, "insufficient_evidence"),
        StateWritePolicy(),
        (CapabilityRequirement("structured_output"),),
        (),
        ArtifactReference(definition.id, V1),
        fallbacks=(
            CapabilityFallback(
                "structured_output",
                "json_fallback",
                validator_ids=("fallback_validator",),
            ),
        ),
        validators=(
            ValidatorDefinition(
                "fallback_validator", V1, "Validate fallback JSON extraction."
            ),
            ValidatorDefinition(
                "explicit_validator", V1, "Validate the candidate batch."
            ),
        ),
    )
    pins = VersionPins(
        ArtifactReference(skill.id, V1),
        ArtifactReference(definition.id, V1),
        ArtifactReference("validator_union_prompt", V1),
        (),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )

    binding = ProfiledCapabilityBinding(
        PROPOSE_FLASHCARDS_MANIFEST,
        PROPOSE_FLASHCARDS_MANIFEST.fingerprint,
        profile,
        skill,
        definition,
        pins,
        "candidates",
        lambda *, context, inputs: (),
    )
    assert binding.skill.validators == skill.validators


def test_profiled_worker_descriptor_keeps_receipt_out_of_public_payload() -> None:
    binding = _profiled_binding(HYBRID_MACRO_DETAIL_V1)
    receipt = ProfileSelectionReceipt(
        HYBRID_MACRO_DETAIL_V1,
        ProfileSelectionMode.DEFAULT,
        ProfileSelectorKind.HOST,
        PrincipalKind.SERVICE,
        ProfileSelectionBasis(),
    )
    expectation_fingerprint = "a" * 64
    task = GenerationWorkerTask(
        "lesson-1:page-0",
        GenerationWorkerTaskKind.FLASHCARD_BUNDLE,
        binding.manifest.id,
        binding.manifest.version,
        binding.manifest_fingerprint,
        binding.manifest.required_authority,
        binding.pins,
        playbook_definition_fingerprint(binding.playbook),
        "en",
        {},
        None,
        (f"profile-sha256:{expectation_fingerprint}",),
        ("evidence:page-0",),
        PUBLIC_INPUTS,
        binding.manifest.output_schema,
        fingerprint_output_schema(binding.manifest.output_schema),
        (
            ValidationExpectation(
                "validate",
                ValidationReceiptSource.VALIDATE_STEP,
                "fixture",
                "1.0.0",
            ),
        ),
    )
    descriptor = ProfiledWorkerExecutionDescriptor(
        binding, receipt, expectation_fingerprint
    )

    execution = descriptor.execution_inputs(task)
    assert task.capability_inputs() == PUBLIC_INPUTS
    assert PROFILE_SELECTION_RECEIPT_INPUT not in task.capability_inputs()
    assert execution[PROFILE_SELECTION_RECEIPT_INPUT] == receipt.to_bytes().decode()

    with pytest.raises(ValueError, match="profile expectation"):
        descriptor.execution_inputs(
            replace(task, index_references=("profile-sha256:" + "b" * 64,))
        )
