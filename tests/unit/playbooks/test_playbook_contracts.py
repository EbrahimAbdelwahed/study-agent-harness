from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from study_agent.domain import RunId
from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueStep,
    ModelStep,
    PlaybookCheckpoint,
    PlaybookDefinition,
    ReadDependency,
    RunStatus,
    StepTrace,
    StepTraceStatus,
    ToolBehaviorPin,
    ToolStep,
    ValidateStep,
    ValidationOutcome,
    ValidatorDisposition,
    VersionPins,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    JsonSchema,
    SemanticVersion,
    VersionRange,
)

V1 = SemanticVersion.parse("1.0.0")
REF = ArtifactReference("grounded_answer", V1)
OBJECT_SCHEMA = JsonSchema({"type": "object"})


def make_steps() -> tuple[ToolStep, ModelStep, DialogueStep, ValidateStep]:
    tool = ToolStep("search", ArtifactReference("source.search", V1), {"query": "Q"}, "evidence")
    model = ModelStep(
        "answer",
        ArtifactReference("grounded_answer_prompt", V1),
        ModelRequest((ModelMessage(MessageRole.USER, "Use supplied evidence."),)),
        OBJECT_SCHEMA,
        "draft",
        (CapabilityRequirement("structured_output"),),
    )
    dialogue = DialogueStep("clarify", "Please clarify the question.", OBJECT_SCHEMA, "reply")
    validate = ValidateStep(
        "check_answer",
        ArtifactReference("citation_validator", V1),
        ("draft", "evidence"),
        "validated",
    )
    return tool, model, dialogue, validate


def test_playbook_accepts_only_the_trusted_sequential_v01_ast() -> None:
    definition = PlaybookDefinition(
        "grounded_answer_flow",
        V1,
        VersionRange(V1, SemanticVersion.parse("2.0.0")),
        make_steps(),
    )
    assert tuple(step.kind for step in definition.steps) == (
        "tool",
        "model",
        "dialogue",
        "validate",
    )

    class BranchStep:
        id = "branch"
        output_key = "branched"

    with pytest.raises(ValueError, match="only tool, model, dialogue, and validate"):
        PlaybookDefinition(
            "bad_flow",
            V1,
            VersionRange(V1, SemanticVersion.parse("2.0.0")),
            (BranchStep(),),  # type: ignore[arg-type]
        )


def test_validate_steps_can_only_consume_prior_outputs() -> None:
    validate = ValidateStep("validate", REF, ("future",), "result")
    tool = ToolStep("future", ArtifactReference("source.search", V1), {}, "future")
    with pytest.raises(ValueError, match="previous step outputs"):
        PlaybookDefinition(
            "invalid_order",
            V1,
            VersionRange(V1, SemanticVersion.parse("2.0.0")),
            (validate, tool),
        )


def test_version_pins_cover_every_reproducibility_boundary() -> None:
    pins = VersionPins(
        skill=REF,
        playbook=ArtifactReference("grounded_answer_flow", V1),
        prompt=ArtifactReference("grounded_answer_prompt", V1),
        tool_behaviors=(ToolBehaviorPin("source.search", V1),),
        model_adapter=ArtifactReference("compatible_model_adapter", V1),
        state_contract=ArtifactReference("event_state", V1),
    )
    assert pins.skill.version == pins.playbook.version == pins.prompt.version == V1
    assert (
        pins.tool_behaviors[0].version
        == pins.model_adapter.version
        == pins.state_contract.version
    )


def test_checkpoint_and_trace_are_immutable_versioned_data_contracts() -> None:
    pins = VersionPins(REF, REF, REF, (), REF, REF)
    checkpoint = PlaybookCheckpoint(
        RunId("run-1"),
        pins,
        RunStatus.SUSPENDED,
        2,
        {"draft": {"status": "answered"}},
        (ReadDependency("source_revision", "revision-1", "checksum-1"),),
        datetime.now(UTC),
    )
    trace = StepTrace("answer", "model", StepTraceStatus.COMPLETED, datetime.now(UTC))

    with pytest.raises(FrozenInstanceError):
        checkpoint.next_step_index = 3  # type: ignore[misc]
    with pytest.raises(TypeError):
        checkpoint.outputs["other"] = {}  # type: ignore[index]
    assert checkpoint.schema_version == 1
    assert trace.step_kind == "model"


def test_playbook_model_metadata_rejects_provider_specific_fields() -> None:
    with pytest.raises(ValueError, match="provider/model-specific"):
        ModelStep(
            "answer",
            REF,
            ModelRequest(
                (ModelMessage(MessageRole.USER, "Answer."),),
                metadata={"provider_options": {"reasoning_effort": "high"}},
            ),
            OBJECT_SCHEMA,
            "draft",
        )


def test_grounded_answer_dataflow_binds_inputs_and_prior_outputs_without_branching() -> None:
    run_question = DataReference(DataSourceKind.RUN_INPUT, "question")
    evidence = DataReference(DataSourceKind.STEP_OUTPUT, "evidence")
    draft = DataReference(DataSourceKind.STEP_OUTPUT, "draft")
    validated = DataReference(DataSourceKind.STEP_OUTPUT, "validated")
    steps = (
        ToolStep(
            "search",
            ArtifactReference("source.search", V1),
            {},
            "evidence",
            (DataBinding("query", run_question),),
        ),
        ValidateStep(
            "evidence_gate",
            ArtifactReference("evidence_validator", V1),
            ("evidence",),
            "sufficient_evidence",
            (DataBinding("evidence", evidence),),
        ),
        ModelStep(
            "answer",
            ArtifactReference("grounded_answer_prompt", V1),
            ModelRequest((ModelMessage(MessageRole.USER, "Use bound prompt inputs."),)),
            OBJECT_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("question", run_question),
                DataBinding("evidence", evidence),
            ),
        ),
        ValidateStep(
            "citation_check",
            ArtifactReference("citation_validator", V1),
            ("draft", "evidence"),
            "validated",
            (
                DataBinding("answer", draft),
                DataBinding("evidence", evidence),
            ),
        ),
        ToolStep(
            "commit",
            ArtifactReference("session.commit_answer", V1),
            {},
            "committed",
            (DataBinding("answer", validated),),
        ),
    )
    definition = PlaybookDefinition(
        "grounded_answer_flow",
        V1,
        VersionRange(V1, SemanticVersion.parse("2.0.0")),
        steps,
        ("question",),
    )

    assert definition.steps == steps
    assert definition.input_keys == ("question",)


def test_dataflow_rejects_future_outputs_and_provider_selectors() -> None:
    future = DataReference(DataSourceKind.STEP_OUTPUT, "future")
    step = ToolStep(
        "search",
        ArtifactReference("source.search", V1),
        {},
        "evidence",
        (DataBinding("query", future),),
    )
    with pytest.raises(ValueError, match="non-previous"):
        PlaybookDefinition(
            "bad_dataflow",
            V1,
            VersionRange(V1, SemanticVersion.parse("2.0.0")),
            (step,),
        )
    with pytest.raises(ValueError, match="provider/model-specific"):
        DataBinding("provider_id", DataReference(DataSourceKind.RUN_INPUT, "question"))


def test_validation_outcome_explicitly_controls_continue_or_terminate() -> None:
    continued = ValidationOutcome(
        True,
        ValidatorDisposition.CONTINUE,
        {"evidence_status": "sufficient"},
    )
    terminated = ValidationOutcome(
        False,
        ValidatorDisposition.TERMINATE,
        {"evidence_status": "insufficient"},
        "Evidence is insufficient.",
    )

    assert continued.disposition is ValidatorDisposition.CONTINUE
    assert terminated.disposition is ValidatorDisposition.TERMINATE
    with pytest.raises(ValueError, match="must terminate"):
        ValidationOutcome(False, ValidatorDisposition.CONTINUE, {})


def test_playbook_collections_are_owned_and_checkpoint_allows_provenance_identity() -> None:
    path = ["answer"]
    bindings = [
        DataBinding(
            "payload",
            DataReference(DataSourceKind.RUN_INPUT, "question", path),  # type: ignore[arg-type]
        )
    ]
    steps = [
        ToolStep(
            "commit",
            ArtifactReference("session.commit_answer", V1),
            {},
            "committed",
            bindings,  # type: ignore[arg-type]
        )
    ]
    definition = PlaybookDefinition(
        "owned_flow",
        V1,
        VersionRange(V1, SemanticVersion.parse("2.0.0")),
        steps,  # type: ignore[arg-type]
        ["question"],  # type: ignore[arg-type]
    )
    dependencies = [ReadDependency("source", "source-1", "v1")]
    checkpoint = PlaybookCheckpoint(
        RunId("run-provider-data"),
        VersionPins(REF, REF, REF, (), REF, REF),
        RunStatus.SUSPENDED,
        1,
        {"provenance": {"provider": "test-provider", "model_id": "test-model"}},
        dependencies,  # type: ignore[arg-type]
        datetime.now(UTC),
    )

    path.append("mutated")
    bindings.clear()
    steps.clear()
    dependencies.clear()

    commit = definition.steps[0]
    assert isinstance(commit, ToolStep)
    assert commit.bindings[0].source.path == ("answer",)
    assert checkpoint.read_dependencies[0].id == "source-1"
    assert checkpoint.outputs["provenance"] == {
        "provider": "test-provider",
        "model_id": "test-model",
    }
