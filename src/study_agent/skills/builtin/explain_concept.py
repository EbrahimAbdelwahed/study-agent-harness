from __future__ import annotations

from study_agent.domain._validation import JsonObject
from study_agent.grounding import GROUNDED_ANSWER_DRAFT_SCHEMA
from study_agent.prompts import EXPLAIN_CONCEPT_LAYERS
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

VERSION = SemanticVersion.parse("1.0.0")
ENGINE_V2 = SemanticVersion.parse("2.0.0")

EXPLAIN_CONCEPT_INPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": (
            "query",
            "target",
            "language",
            "learner_goal",
            "continuation_summary_json",
        ),
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "target": {"type": ("string", "null")},
            "language": {"type": "string", "minLength": 1},
            "learner_goal": {"type": ("string", "null")},
            "continuation_summary_json": {"type": ("string", "null")},
        },
    }
)

_CITATION_SCHEMA: JsonObject = {
    "type": "object",
    "required": (
        "source_id",
        "revision_id",
        "chunk_id",
        "start_offset",
        "end_offset",
        "locator",
        "quoted_snippet",
    ),
    "additionalProperties": False,
    "properties": {
        "source_id": {"type": "string"},
        "revision_id": {"type": "string"},
        "chunk_id": {"type": "string"},
        "start_offset": {"type": "integer"},
        "end_offset": {"type": "integer"},
        "locator": {"type": "string"},
        "quoted_snippet": {"type": "string"},
    },
}

EXPLAIN_CONCEPT_OUTPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("status", "segments", "unsupported_information_note"),
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ("answered",)},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ("kind", "text", "citations"),
                    "additionalProperties": False,
                    "properties": {
                        "kind": {"type": "string"},
                        "text": {"type": "string"},
                        "citations": {"type": "array", "items": _CITATION_SCHEMA},
                    },
                },
            },
            "unsupported_information_note": {"type": ("string", "null")},
        },
    }
)

EXPLAIN_CONCEPT_MODEL_SCHEMA = GROUNDED_ANSWER_DRAFT_SCHEMA

EXPLAIN_CONCEPT_SKILL = SkillPackage(
    id="explain_concept",
    version=VERSION,
    purpose="Explain one bounded concept from canonically resolvable course evidence.",
    engine_compatibility=VersionRange(VERSION, ENGINE_V2),
    input_schema=EXPLAIN_CONCEPT_INPUT_SCHEMA,
    output_schema=EXPLAIN_CONCEPT_OUTPUT_SCHEMA,
    prompt_layers=EXPLAIN_CONCEPT_LAYERS,
    course_profile_fields=(),
    grounding_policy=GroundingPolicy(True, "insufficient_evidence", True),
    state_write_policy=StateWritePolicy(),
    required_capabilities=(CapabilityRequirement("structured_output"),),
    required_tools=(ToolRequirement("source.search", VERSION),),
    playbook=ArtifactReference("explain_concept_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("explain_concept_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "tutor_evidence_gate",
            VERSION,
            "Terminate before tutoring when evidence is insufficient or conflicting.",
        ),
        ValidatorDefinition(
            "explain_concept_readiness",
            VERSION,
            "Request clarification only when the trusted target is absent.",
        ),
        ValidatorDefinition(
            "explain_concept_integrity",
            VERSION,
            "Resolve every explanation citation against canonical source content.",
        ),
    ),
    known_failure_modes=(
        "insufficient or conflicting trusted evidence",
        "unknown evidence handle",
        "canonical citation resolution failure",
    ),
)
