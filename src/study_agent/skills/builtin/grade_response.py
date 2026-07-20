"""Provider-neutral, read-only free-response grading skill."""

from study_agent.domain._validation import JsonObject
from study_agent.prompts.grade_response_v1 import GRADE_RESPONSE_LAYERS
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

GRADE_RESPONSE_INPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("attempt_id", "language"),
        "additionalProperties": False,
        "properties": {
            "attempt_id": {"type": "string", "minLength": 1},
            "language": {"type": "string", "minLength": 1},
        },
    }
)

_CRITERION_MODEL: JsonObject = {
    "type": "object",
    "required": (
        "criterion",
        "status",
        "rationale",
        "evidence_ids",
        "confidence",
        "evidence_insufficient",
    ),
    "additionalProperties": False,
    "properties": {
        "criterion": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ("met", "not_met", "uncertain")},
        "rationale": {"type": "string", "minLength": 1},
        "evidence_ids": {
            "type": "array",
            "maxItems": 32,
            "items": {"type": "string", "minLength": 1},
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_insufficient": {"type": "boolean"},
    },
}

GRADE_RESPONSE_MODEL_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("criteria",),
        "additionalProperties": False,
        "properties": {
            "criteria": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _CRITERION_MODEL,
            }
        },
    }
)

_CRITERION_FINAL: JsonObject = {
    **_CRITERION_MODEL,
}
GRADE_RESPONSE_OUTPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("status", "criteria", "score"),
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ("graded", "needs_review", "ungradable"),
            },
            "criteria": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "items": _CRITERION_FINAL,
            },
            "score": {
                "type": "object",
                "required": ("numerator", "denominator"),
                "additionalProperties": False,
                "properties": {
                    "numerator": {"type": "integer", "minimum": 0},
                    "denominator": {"type": "integer", "minimum": 1},
                },
            },
        },
    }
)

GRADE_RESPONSE_SKILL = SkillPackage(
    "grade_response",
    VERSION,
    "Evaluate one immutable free-response attempt without writing canonical state.",
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    GRADE_RESPONSE_INPUT_SCHEMA,
    GRADE_RESPONSE_OUTPUT_SCHEMA,
    GRADE_RESPONSE_LAYERS,
    (),
    GroundingPolicy(True, "insufficient_evidence", True),
    StateWritePolicy(),
    (CapabilityRequirement("structured_output"),),
    (ToolRequirement("assessment.prepare_grade_scope", VERSION),),
    ArtifactReference("grade_response_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("grade_response_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "grade_response_readiness",
            VERSION,
            "Validate request-bound scope, bounds, and untrusted-data separation.",
        ),
        ValidatorDefinition(
            "grade_response_integrity",
            VERSION,
            "Re-resolve evidence and derive the final status and exact rational score.",
        ),
    ),
    known_failure_modes=(
        "stale attempt, presentation, rubric, or accepted artifact",
        "missing, duplicate, or reordered criterion",
        "unknown or stale evidence handle",
        "provider, tool, learner advice, mastery, or scheduling field",
    ),
)

__all__ = [
    "GRADE_RESPONSE_INPUT_SCHEMA",
    "GRADE_RESPONSE_MODEL_SCHEMA",
    "GRADE_RESPONSE_OUTPUT_SCHEMA",
    "GRADE_RESPONSE_SKILL",
    "VERSION",
]
