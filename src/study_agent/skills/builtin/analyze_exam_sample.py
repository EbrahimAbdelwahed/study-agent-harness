"""Provider-neutral skill for observational exam-sample analysis."""

from study_agent.domain._validation import JsonObject
from study_agent.prompts.exam_sample_analysis_v1 import EXAM_SAMPLE_ANALYSIS_LAYERS
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
EXAM_ANALYSIS_INPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("sample_revision_ids", "language"),
        "additionalProperties": False,
        "properties": {
            "sample_revision_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": 16,
                "items": {"type": "string", "minLength": 1},
            },
            "language": {"type": "string", "minLength": 1},
        },
    }
)
_OBSERVATION: JsonObject = {
    "type": "object",
    "required": ("value", "evidence_ids"),
    "additionalProperties": False,
    "properties": {
        "value": {"type": "string", "minLength": 1},
        "evidence_ids": {
            "type": "array",
            "minItems": 1,
            "maxItems": 16,
            "items": {"type": "string", "minLength": 1},
        },
    },
}
EXAM_ANALYSIS_MODEL_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("observed_topics", "observed_formats"),
        "additionalProperties": False,
        "properties": {
            "observed_topics": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _OBSERVATION,
            },
            "observed_formats": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _OBSERVATION,
            },
        },
    }
)
EXAM_ANALYSIS_OUTPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("sample_size", "observed_topics", "observed_formats", "limitations"),
        "additionalProperties": False,
        "properties": {
            "sample_size": {"type": "integer", "minimum": 1, "maximum": 16},
            "observed_topics": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _OBSERVATION,
            },
            "observed_formats": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _OBSERVATION,
            },
            "limitations": {
                "type": "array",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string", "minLength": 1},
            },
        },
    }
)

ANALYZE_EXAM_SAMPLE_SKILL = SkillPackage(
    "analyze_exam_sample",
    VERSION,
    "Describe grounded topic and format observations from selected exam samples.",
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    EXAM_ANALYSIS_INPUT_SCHEMA,
    EXAM_ANALYSIS_OUTPUT_SCHEMA,
    EXAM_SAMPLE_ANALYSIS_LAYERS,
    (),
    GroundingPolicy(True, "insufficient_evidence", True),
    StateWritePolicy(),
    (CapabilityRequirement("structured_output"),),
    (ToolRequirement("source.prepare_exam_sample_scope", VERSION),),
    ArtifactReference("analyze_exam_sample_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("exam_blueprint_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "exam_sample_readiness", VERSION, "Validate exact complete sample evidence."
        ),
        ValidatorDefinition(
            "exam_blueprint_integrity", VERSION, "Validate observational grounded output."
        ),
    ),
)

__all__ = [
    "ANALYZE_EXAM_SAMPLE_SKILL",
    "EXAM_ANALYSIS_INPUT_SCHEMA",
    "EXAM_ANALYSIS_MODEL_SCHEMA",
    "EXAM_ANALYSIS_OUTPUT_SCHEMA",
    "VERSION",
]
