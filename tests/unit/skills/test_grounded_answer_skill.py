from collections.abc import Mapping
from typing import cast

from study_agent.domain._validation import JsonValue
from study_agent.ports import ModelCapabilities
from study_agent.prompts import GROUNDED_ANSWER_LAYERS
from study_agent.skills import (
    NegotiationStatus,
    PromptLayerKind,
    SemanticVersion,
    negotiate_capabilities,
)
from study_agent.skills.builtin import (
    GROUNDED_ANSWER_MODEL_SCHEMA,
    GROUNDED_ANSWER_SKILL,
)


def test_grounded_answer_skill_has_canonical_ids_and_behavior_contracts() -> None:
    skill = GROUNDED_ANSWER_SKILL

    assert skill.id == "grounded_answer"
    assert skill.version == SemanticVersion.parse("1.0.0")
    assert skill.playbook.id == "grounded_answer_flow"
    assert skill.prompt_layers == GROUNDED_ANSWER_LAYERS
    assert tuple(layer.kind for layer in skill.prompt_layers) == tuple(PromptLayerKind)
    assert {item.id for item in skill.validators} == {
        "evidence_sufficiency",
        "grounded_answer_integrity",
    }
    assert {item.name for item in skill.required_tools} == {
        "session.get_context",
        "source.search",
    }
    assert skill.state_write_policy.allowed_event_types == (
        "session.interaction_recorded",
        "session.answer_recorded",
        "session.continuation_summary_updated",
    )


def test_grounded_answer_declares_portable_structured_output_fallback() -> None:
    skill = GROUNDED_ANSWER_SKILL

    assert len(skill.fallbacks) == 1
    fallback = skill.fallbacks[0]
    assert fallback.missing_capability == "structured_output"
    assert fallback.strategy == "parse_json_then_validate"
    assert fallback.validator_ids == ("grounded_answer_integrity",)
    assert negotiate_capabilities(skill, ModelCapabilities()).status is (
        NegotiationStatus.DECLARED_FALLBACK
    )


def test_model_schema_is_strict_and_exposes_only_handles() -> None:
    schema = GROUNDED_ANSWER_MODEL_SCHEMA.value
    properties = schema["properties"]
    typed_properties = cast(Mapping[str, JsonValue], properties)

    assert schema["additionalProperties"] is False
    assert set(typed_properties) == {
        "status",
        "segments",
        "unsupported_information_note",
    }
    segments_schema = cast(Mapping[str, JsonValue], typed_properties["segments"])
    segment = cast(Mapping[str, JsonValue], segments_schema["items"])
    assert segment["additionalProperties"] is False
    segment_properties = cast(Mapping[str, JsonValue], segment["properties"])
    assert set(segment_properties) == {"kind", "text", "evidence_ids"}
