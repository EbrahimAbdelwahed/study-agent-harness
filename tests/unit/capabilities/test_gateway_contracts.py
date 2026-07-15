from __future__ import annotations

from dataclasses import replace

import pytest

from study_agent.capabilities import (
    CancelledCapabilityOutcome,
    CapabilityBinding,
    CapabilityContinuation,
    CapabilityGatewayError,
    CapabilityGatewayErrorCode,
    CapabilityManifest,
    CompletedCapabilityOutcome,
    FailedCapabilityOutcome,
    StaleCapabilityOutcome,
    SuspendedCapabilityOutcome,
    TerminatedCapabilityOutcome,
    TutorCapabilityId,
)
from study_agent.domain import ExecutionContext, RunId
from study_agent.domain._validation import JsonObject
from study_agent.playbooks import (
    ModelStep,
    PlaybookDefinition,
    PlaybookRunStatus,
    ReadDependency,
    ToolBehaviorPin,
    ToolStep,
    ValidationOutcome,
    ValidatorDisposition,
    VerifiedRunRecord,
    VersionPins,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest
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


def _manifest(*, suspension: bool = False) -> CapabilityManifest:
    return CapabilityManifest(
        TutorCapabilityId.EXPLAIN_CONCEPT,
        V1,
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        ("study:explain",),
        suspension,
    )


def _playbook() -> PlaybookDefinition:
    return PlaybookDefinition(
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


def _skill(
    playbook: PlaybookDefinition,
    *,
    identifier: str = "explain_concept",
    input_schema: JsonSchema | None = None,
    output_schema: JsonSchema | None = None,
) -> SkillPackage:
    return SkillPackage(
        identifier,
        V1,
        "Explain one learner-selected concept.",
        VersionRange(V1, V2),
        input_schema or JsonSchema(INPUT_SCHEMA),
        output_schema or JsonSchema(OUTPUT_SCHEMA),
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
        ArtifactReference(playbook.id, playbook.version),
    )


def _pins(
    skill: SkillPackage, playbook: PlaybookDefinition
) -> VersionPins:
    return VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(playbook.id, playbook.version),
        ArtifactReference("explain_prompt", V1),
        (ToolBehaviorPin("fixture.answer", V1),),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )


def _resolve_dependencies(
    *, context: ExecutionContext, inputs: JsonObject
) -> tuple[ReadDependency, ...]:
    del context, inputs
    return ()


def _binding(
    *,
    manifest: CapabilityManifest | None = None,
    manifest_fingerprint: str | None = None,
    skill: SkillPackage | None = None,
    playbook: PlaybookDefinition | None = None,
    pins: VersionPins | None = None,
    output_key: str = "answer",
) -> CapabilityBinding:
    selected_manifest = manifest or _manifest()
    selected_playbook = playbook or _playbook()
    selected_skill = skill or _skill(selected_playbook)
    return CapabilityBinding(
        selected_manifest,
        manifest_fingerprint or selected_manifest.fingerprint,
        selected_skill,
        selected_playbook,
        pins or _pins(selected_skill, selected_playbook),
        output_key,
        _resolve_dependencies,
    )


def test_valid_binding_is_immutable_and_owns_exact_portable_contract() -> None:
    binding = _binding()
    assert binding.manifest.id is TutorCapabilityId.EXPLAIN_CONCEPT
    assert binding.skill.id == binding.manifest.id.value
    assert binding.playbook.input_keys == ("topic",)
    assert binding.output_key == "answer"
    assert binding.manifest_fingerprint == binding.manifest.fingerprint


@pytest.mark.parametrize(
    ("manifest_fingerprint", "output_key", "manifest", "match"),
    (
        ("0" * 64, "answer", None, "manifest fingerprint"),
        (None, "missing", None, "output key"),
        (None, "answer", _manifest(suspension=True), "suspension"),
    ),
)
def test_binding_rejects_manifest_output_and_suspension_mismatch(
    manifest_fingerprint: str | None,
    output_key: str,
    manifest: CapabilityManifest | None,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _binding(
            manifest_fingerprint=manifest_fingerprint,
            output_key=output_key,
            manifest=manifest,
        )


def test_binding_rejects_skill_playbook_pin_and_schema_mismatch() -> None:
    playbook = _playbook()
    wrong_skill = _skill(playbook, identifier="assess_understanding")
    with pytest.raises(ValueError, match="skill identity"):
        _binding(skill=wrong_skill, pins=_pins(wrong_skill, playbook))

    skill = _skill(playbook)
    wrong_playbook = replace(playbook, id="other_flow")
    with pytest.raises(ValueError, match="playbook"):
        _binding(
            playbook=wrong_playbook,
            skill=skill,
            pins=_pins(skill, playbook),
        )
    with pytest.raises(ValueError, match="skill pin"):
        _binding(pins=replace(_pins(skill, playbook), skill=ArtifactReference("other", V1)))
    with pytest.raises(ValueError, match="input schema"):
        _binding(
            skill=_skill(
                playbook,
                input_schema=JsonSchema(
                    {
                        "type": "object",
                        "required": ("question",),
                        "properties": {"question": {"type": "string"}},
                        "additionalProperties": False,
                    }
                ),
            )
        )
    with pytest.raises(ValueError, match="output schema"):
        _binding(
            skill=_skill(
                playbook,
                output_schema=JsonSchema(
                    {
                        "type": "object",
                        "required": ("result",),
                        "properties": {"result": {"type": "string"}},
                        "additionalProperties": False,
                    }
                ),
            )
        )


@pytest.mark.parametrize(
    "tool_behaviors",
    (
        (),
        (ToolBehaviorPin("fixture.answer", V2),),
        (
            ToolBehaviorPin("fixture.answer", V1),
            ToolBehaviorPin("fixture.extra", V1),
        ),
    ),
)
def test_binding_rejects_missing_wrong_and_extra_tool_behavior_pins(
    tool_behaviors: tuple[ToolBehaviorPin, ...],
) -> None:
    playbook = _playbook()
    skill = _skill(playbook)
    pins = replace(_pins(skill, playbook), tool_behaviors=tool_behaviors)
    with pytest.raises(ValueError, match="tool behavior pins"):
        _binding(playbook=playbook, skill=skill, pins=pins)


def test_binding_rejects_model_step_that_differs_from_prompt_pin() -> None:
    prompt = ArtifactReference("explain_prompt", V1)
    playbook = PlaybookDefinition(
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
    skill = replace(_skill(playbook), required_tools=())
    pins = VersionPins(
        ArtifactReference(skill.id, skill.version),
        ArtifactReference(playbook.id, playbook.version),
        ArtifactReference("wrong_prompt", V1),
        (),
        ArtifactReference("fixture_model", V1),
        ArtifactReference("event_state", V1),
    )
    with pytest.raises(ValueError, match="model-step prompt"):
        _binding(playbook=playbook, skill=skill, pins=pins)


def _continuation() -> CapabilityContinuation:
    binding = _binding()
    return CapabilityContinuation(
        RunId("run-1"),
        binding.manifest.id,
        binding.manifest.version,
        binding.manifest.fingerprint,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "clarify",
        1,
        {"topic": "aortic valve"},
        binding.pins,
        (ReadDependency("course", "course-1", "sequence-1"),),
    )


def _verified(status: PlaybookRunStatus) -> VerifiedRunRecord:
    termination = (
        ValidationOutcome(True, ValidatorDisposition.TERMINATE, {}, "safe stop")
        if status is PlaybookRunStatus.TERMINATED
        else None
    )
    return VerifiedRunRecord(
        RunId("run-1"),
        "c" * 64,
        {"topic": "aortic valve"},
        _binding().pins,
        (),
        {"answer": {"answer": "Three cusps."}},
        (),
        status,
        termination,
    )


def test_continuation_and_outcomes_keep_success_proof_at_exact_boundary() -> None:
    continuation = _continuation()
    assert continuation.fingerprint == _continuation().fingerprint
    suspended = SuspendedCapabilityOutcome(
        continuation.run_id, "Clarify the target.", continuation
    )
    completed = CompletedCapabilityOutcome(
        _verified(PlaybookRunStatus.COMPLETED), {"answer": "Three cusps."}
    )
    terminated = TerminatedCapabilityOutcome(_verified(PlaybookRunStatus.TERMINATED))
    assert completed.run.status is PlaybookRunStatus.COMPLETED
    assert terminated.run.status is PlaybookRunStatus.TERMINATED
    assert suspended.continuation is continuation

    non_success = (
        CancelledCapabilityOutcome(RunId("cancelled"), "cancelled"),
        FailedCapabilityOutcome(RunId("failed"), "failed"),
        StaleCapabilityOutcome(RunId("stale"), "stale"),
    )
    assert all(not hasattr(item, "run") for item in non_success)
    assert all(not hasattr(item, "output") for item in non_success)


def test_gateway_error_retryability_is_closed_to_in_progress() -> None:
    retryable = CapabilityGatewayError(
        CapabilityGatewayErrorCode.IN_PROGRESS,
        "winner is still running",
        retryable=True,
    )
    assert retryable.retryable is True
    with pytest.raises(ValueError, match="only in_progress"):
        CapabilityGatewayError(
            CapabilityGatewayErrorCode.CONFLICT,
            "not retryable",
            retryable=True,
        )
