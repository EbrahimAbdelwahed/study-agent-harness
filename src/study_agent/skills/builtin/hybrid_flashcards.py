"""Private skill package for the hybrid macro-detail flashcard profile."""

from __future__ import annotations

from study_agent.domain._validation import JsonObject
from study_agent.prompts.hybrid_flashcards_v1 import HYBRID_FLASHCARDS_LAYERS
from study_agent.skills import (
    ArtifactReference,
    CapabilityFallback,
    CapabilityRequirement,
    GroundingPolicy,
    JsonSchema,
    SemanticVersion,
    SkillPackage,
    StateWritePolicy,
    ToolRequirement,
    ValidatorDefinition,
    VersionRange,
)
from study_agent.skills.builtin.propose_flashcards import (
    PROPOSE_FLASHCARDS_INPUT_SCHEMA,
    PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
)

VERSION = SemanticVersion.parse("1.0.0")
ENGINE_V2 = SemanticVersion.parse("2.0.0")

_ANSWER_BLOCK_SCHEMA: JsonObject = {
    "type": "object",
    "required": ("label", "text", "key_points"),
    "additionalProperties": False,
    "properties": {
        "label": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "key_points": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "maxItems": 12,
        },
    },
}

_CANDIDATE_SCHEMA: JsonObject = {
    "type": "object",
    "required": (
        "candidate_key",
        "parent_candidate_key",
        "retrieval_form",
        "prompt",
        "answer_blocks",
        "pedagogical_role",
        "morphology_family",
        "cognitive_function",
        "rationale",
        "evidence_ids",
        "media_evidence_ids",
    ),
    "additionalProperties": False,
    "properties": {
        "candidate_key": {"type": "string", "minLength": 1},
        "parent_candidate_key": {"type": ("string", "null")},
        "retrieval_form": {"type": "string", "enum": ("direct_recall", "contextual_gap")},
        "prompt": {"type": "string", "minLength": 1},
        "answer_blocks": {
            "type": "array",
            "items": _ANSWER_BLOCK_SCHEMA,
            "minItems": 1,
            "maxItems": 8,
        },
        "pedagogical_role": {"type": "string", "enum": ("section", "detail")},
        "morphology_family": {"type": "null"},
        "cognitive_function": {"type": "null"},
        "rationale": {"type": "string", "minLength": 1},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": 16,
        },
        "media_evidence_ids": {"type": "array", "maxItems": 0},
    },
}

_OMISSION_SCHEMA: JsonObject = {
    "type": "object",
    "required": ("reason", "evidence_ids"),
    "additionalProperties": False,
    "properties": {
        "reason": {"type": "string", "minLength": 1},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "maxItems": 16,
        },
    },
}

HYBRID_FLASHCARDS_MODEL_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("topic_plan", "candidates", "omissions", "detail_bases"),
        "additionalProperties": False,
        "properties": {
            "topic_plan": {
                "type": "array",
                "minItems": 1,
                "maxItems": 256,
                "items": {
                    "type": "object",
                    "required": ("topic_key", "disposition", "candidate_keys", "omission_reason"),
                    "additionalProperties": False,
                    "properties": {
                        "topic_key": {"type": "string", "minLength": 1},
                        "disposition": {
                            "type": "string",
                            "enum": ("generate", "omit_scaffolding", "omit"),
                        },
                        "candidate_keys": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "maxItems": 24,
                            "uniqueItems": True,
                        },
                        "omission_reason": {"type": ("string", "null")},
                    },
                },
            },
            "candidates": {"type": "array", "items": _CANDIDATE_SCHEMA, "maxItems": 24},
            "omissions": {"type": "array", "items": _OMISSION_SCHEMA, "maxItems": 24},
            "detail_bases": {
                "type": "array",
                "maxItems": 24,
                "items": {
                    "type": "object",
                    "required": ("candidate_key", "basis"),
                    "additionalProperties": False,
                    "properties": {
                        "candidate_key": {"type": "string", "minLength": 1},
                        "basis": {"type": "string", "enum": ("fragile", "not_recoverable")},
                    },
                },
            },
        },
    }
)

HYBRID_FLASHCARDS_SKILL = SkillPackage(
    id="propose_flashcards_hybrid",
    version=VERSION,
    purpose="Propose grounded section frameworks followed by earned detail flashcards.",
    engine_compatibility=VersionRange(VERSION, ENGINE_V2),
    input_schema=PROPOSE_FLASHCARDS_INPUT_SCHEMA,
    output_schema=PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
    prompt_layers=HYBRID_FLASHCARDS_LAYERS,
    course_profile_fields=(),
    grounding_policy=GroundingPolicy(True, "insufficient_evidence", True),
    state_write_policy=StateWritePolicy(),
    required_capabilities=(CapabilityRequirement("structured_output"),),
    required_tools=(ToolRequirement("source.prepare_planned_flashcard_scope", VERSION),),
    playbook=ArtifactReference("propose_flashcards_hybrid_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("hybrid_flashcards_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "hybrid_flashcards_readiness",
            VERSION,
            "Require a valid prepared scope with sufficient active evidence.",
        ),
        ValidatorDefinition(
            "hybrid_flashcards_integrity",
            VERSION,
            "Validate the full plan, hierarchy, budgets, uniqueness, and grounding.",
        ),
    ),
    known_failure_modes=(
        "insufficient or conflicting prepared evidence",
        "incomplete or reordered active-bundle topic plan",
        "unlinked or stale evidence",
        "invalid hierarchy, duplicate content, or ceiling excess",
    ),
)

__all__ = ["HYBRID_FLASHCARDS_MODEL_SCHEMA", "HYBRID_FLASHCARDS_SKILL", "VERSION"]
