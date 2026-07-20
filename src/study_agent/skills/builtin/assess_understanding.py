from __future__ import annotations

from study_agent.domain._validation import JsonObject
from study_agent.prompts import ASSESS_UNDERSTANDING_LAYERS
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

ASSESS_UNDERSTANDING_INPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": (
            "query",
            "scope",
            "assessment_format",
            "question_count",
            "language",
            "continuation_summary_json",
        ),
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "scope": {"type": ("string", "null")},
            "assessment_format": {"type": ("string", "null")},
            "question_count": {"type": "integer", "minimum": 1, "maximum": 10},
            "language": {"type": "string", "minLength": 1},
            "continuation_summary_json": {"type": ("string", "null")},
        },
    }
)

ASSESS_UNDERSTANDING_MODEL_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("questions",),
        "additionalProperties": False,
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ("kind", "prompt", "options", "evidence_ids"),
                    "additionalProperties": False,
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ("free_response", "multiple_choice"),
                        },
                        "prompt": {"type": "string"},
                        "options": {"type": "array", "items": {"type": "string"}},
                        "evidence_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            }
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

ASSESS_UNDERSTANDING_OUTPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("questions",),
        "additionalProperties": False,
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ("id", "kind", "prompt", "options", "citations"),
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": ("free_response", "multiple_choice"),
                        },
                        "prompt": {"type": "string"},
                        "options": {"type": "array", "items": {"type": "string"}},
                        "citations": {"type": "array", "items": _CITATION_SCHEMA},
                    },
                },
            }
        },
    }
)

ASSESS_UNDERSTANDING_SKILL = SkillPackage(
    id="assess_understanding",
    version=VERSION,
    purpose="Generate evidence-grounded questions without answers or learner evaluation.",
    engine_compatibility=VersionRange(VERSION, ENGINE_V2),
    input_schema=ASSESS_UNDERSTANDING_INPUT_SCHEMA,
    output_schema=ASSESS_UNDERSTANDING_OUTPUT_SCHEMA,
    prompt_layers=ASSESS_UNDERSTANDING_LAYERS,
    course_profile_fields=(),
    grounding_policy=GroundingPolicy(True, "insufficient_evidence", True),
    state_write_policy=StateWritePolicy(),
    required_capabilities=(CapabilityRequirement("structured_output"),),
    required_tools=(ToolRequirement("source.search", VERSION),),
    playbook=ArtifactReference("assess_understanding_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("assess_understanding_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "tutor_evidence_gate",
            VERSION,
            "Terminate before tutoring when evidence is insufficient or conflicting.",
        ),
        ValidatorDefinition(
            "assess_understanding_readiness",
            VERSION,
            "Request clarification only when the trusted scope is absent.",
        ),
        ValidatorDefinition(
            "assess_understanding_integrity",
            VERSION,
            "Validate questions and resolve their canonical source citations.",
        ),
    ),
    known_failure_modes=(
        "insufficient or conflicting trusted evidence",
        "unknown evidence handle",
        "answer or grading field in model output",
        "canonical citation resolution failure",
    ),
)
