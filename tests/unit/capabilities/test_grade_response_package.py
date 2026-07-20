from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from study_agent.assessments import grade_response_binding
from study_agent.capabilities import (
    GRADE_RESPONSE_MANIFEST,
    TutorCapabilityId,
    builtin_tutor_validators,
)
from study_agent.capabilities.bindings import CapabilityDependencyResolver
from study_agent.domain._validation import JsonValue
from study_agent.playbooks import ModelStep, ToolStep, ValidateStep
from study_agent.playbooks.builtin import GRADE_RESPONSE_FLOW
from study_agent.ports import SourceContentPort
from study_agent.prompts import GRADE_RESPONSE_LAYERS, GRADE_RESPONSE_PROMPT
from study_agent.skills import ArtifactReference, SemanticVersion
from study_agent.skills.builtin import (
    GRADE_RESPONSE_MODEL_SCHEMA,
    GRADE_RESPONSE_OUTPUT_SCHEMA,
    GRADE_RESPONSE_SKILL,
)
from study_agent.tools import public_study_tool_manifests
from study_agent.tools.schema import SchemaValidationError, validate_json

V1 = SemanticVersion.parse("1.0.0")


def _resolver(*, context: object, inputs: object) -> tuple[object, ...]:
    del context, inputs
    return ()


class _Content:
    def resolve(self, citation: object) -> object:
        raise AssertionError("validator registry construction must not read content")

    def get_text(self, revision_id: object) -> str:
        raise AssertionError("validator registry construction must not read content")


def test_grade_response_public_surface_is_caller_minimal_and_provider_neutral() -> None:
    schema = GRADE_RESPONSE_MANIFEST.input_schema
    properties = cast(Mapping[str, JsonValue], schema["properties"])

    assert GRADE_RESPONSE_MANIFEST.id is TutorCapabilityId.GRADE_RESPONSE
    assert tuple(properties) == ("attempt_id", "language")
    assert schema["required"] == ("attempt_id", "language")
    assert schema["additionalProperties"] is False
    assert GRADE_RESPONSE_MANIFEST.supports_suspension is False
    assert not {
        "provider",
        "model",
        "rubric",
        "response",
        "evidence",
        "repository",
        "authority",
    }.intersection(properties)
    with pytest.raises(SchemaValidationError):
        validate_json(
            {"attempt_id": "attempt", "language": "Italian", "model": "forged"},
            schema,
        )


def test_model_and_final_schemas_keep_derived_authority_out_of_model_output() -> None:
    model = GRADE_RESPONSE_MODEL_SCHEMA.value
    final = GRADE_RESPONSE_OUTPUT_SCHEMA.value
    model_properties = cast(Mapping[str, JsonValue], model["properties"])
    final_properties = cast(Mapping[str, JsonValue], final["properties"])

    assert tuple(model_properties) == ("criteria",)
    assert tuple(final_properties) == ("status", "criteria", "score")
    assert model["additionalProperties"] is False
    assert final["additionalProperties"] is False
    with pytest.raises(SchemaValidationError):
        validate_json(
            {
                "criteria": (),
                "status": "graded",
                "score": {"numerator": 1, "denominator": 1},
            },
            model,
        )


def test_flow_is_exactly_tool_validate_model_validate_without_dialogue_or_writes() -> None:
    assert tuple(type(step) for step in GRADE_RESPONSE_FLOW.steps) == (
        ToolStep,
        ValidateStep,
        ModelStep,
        ValidateStep,
    )
    assert sum(isinstance(step, ModelStep) for step in GRADE_RESPONSE_FLOW.steps) == 1
    assert GRADE_RESPONSE_FLOW.input_keys == ("attempt_id", "language")
    assert GRADE_RESPONSE_SKILL.state_write_policy.allowed_event_types == ()
    assert GRADE_RESPONSE_SKILL.playbook == ArtifactReference("grade_response_flow", V1)
    tool, readiness, model, integrity = GRADE_RESPONSE_FLOW.steps
    assert isinstance(tool, ToolStep)
    assert isinstance(readiness, ValidateStep)
    assert isinstance(model, ModelStep)
    assert isinstance(integrity, ValidateStep)
    assert tool.tool == ArtifactReference("assessment.prepare_grade_scope", V1)
    assert readiness.validator == ArtifactReference("grade_response_readiness", V1)
    assert model.prompt == GRADE_RESPONSE_PROMPT
    assert integrity.validator == ArtifactReference("grade_response_integrity", V1)


def test_prompt_security_and_version_pins_are_complete_and_cross_wiring_fails() -> None:
    binding = grade_response_binding(
        dependency_resolver=cast(CapabilityDependencyResolver, _resolver),
        model_adapter=ArtifactReference("scripted_model", V1),
        state_contract=ArtifactReference("event_state", V1),
    )
    combined = " ".join(layer.template.lower() for layer in GRADE_RESPONSE_LAYERS)

    assert binding.manifest is GRADE_RESPONSE_MANIFEST
    assert binding.output_key == "grade"
    assert binding.pins.prompt == GRADE_RESPONSE_PROMPT
    assert binding.pins.tool_behaviors[0].tool_name == "assessment.prepare_grade_scope"
    assert {item.id for item in GRADE_RESPONSE_SKILL.validators} == {
        "grade_response_readiness",
        "grade_response_integrity",
    }
    for forbidden_authority in (
        "untrusted data",
        "never instructions",
        "providers",
        "advice",
        "mastery",
        "scheduling",
        "do not author an overall status or score",
    ):
        assert forbidden_authority in combined


def test_capability_vocabulary_is_closed_and_public_study_tools_stay_exactly_seven() -> None:
    assert tuple(item.value for item in TutorCapabilityId) == (
        "explain_concept",
        "assess_understanding",
        "propose_flashcards",
        "analyze_exam_sample",
        "grade_response",
    )
    assert tuple(item.name for item in public_study_tool_manifests()) == (
        "citation.resolve",
        "course.get",
        "grounding.ask",
        "session.get_context",
        "session.record_note",
        "source.list",
        "source.search",
    )


def test_standard_validator_registry_includes_grade_response_pair() -> None:
    validators = builtin_tutor_validators(cast(SourceContentPort, _Content()))

    assert {item.id for item in validators} >= {
        "grade_response_readiness",
        "grade_response_integrity",
    }
