"""Private skill package for morphology-first anatomy flashcards."""

from study_agent.prompts.morphology_flashcards_v1 import MORPHOLOGY_FLASHCARDS_LAYERS
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
_PUBLIC_PROPERTIES = PROPOSE_FLASHCARDS_OUTPUT_SCHEMA.value["properties"]
assert isinstance(_PUBLIC_PROPERTIES, dict | type(PROPOSE_FLASHCARDS_OUTPUT_SCHEMA.value))

MORPHOLOGY_FLASHCARDS_MODEL_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("object_plans", "candidates", "omissions", "topic_omissions"),
        "additionalProperties": False,
        "properties": {
            "object_plans": {
                "type": "array",
                "maxItems": 16,
                "items": {
                    "type": "object",
                    "required": (
                        "topic_keys",
                        "macro_candidate_key",
                        "atomic_candidate_keys",
                        "reconstruction_dimensions",
                    ),
                    "additionalProperties": False,
                    "properties": {
                        "topic_keys": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 16,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "macro_candidate_key": {"type": "string", "minLength": 1},
                        "atomic_candidate_keys": {
                            "type": "array",
                            "maxItems": 3,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "reconstruction_dimensions": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 5,
                            "uniqueItems": True,
                            "items": {
                                "type": "string",
                                "enum": (
                                    "components",
                                    "topology",
                                    "relations",
                                    "course",
                                    "profiles",
                                    "landmarks",
                                ),
                            },
                        },
                    },
                },
            },
            "candidates": _PUBLIC_PROPERTIES["candidates"],
            "omissions": _PUBLIC_PROPERTIES["omissions"],
            "topic_omissions": {
                "type": "array",
                "maxItems": 24,
                "items": {
                    "type": "object",
                    "required": ("topic_key", "omission_index"),
                    "additionalProperties": False,
                    "properties": {
                        "topic_key": {"type": "string", "minLength": 1},
                        "omission_index": {"type": "integer", "minimum": 0, "maximum": 23},
                    },
                },
            },
        },
    }
)

MORPHOLOGY_FLASHCARDS_SKILL = SkillPackage(
    "propose_flashcards_morphology",
    VERSION,
    "Propose anatomy reconstruction cards followed by earned discriminations.",
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    PROPOSE_FLASHCARDS_INPUT_SCHEMA,
    PROPOSE_FLASHCARDS_OUTPUT_SCHEMA,
    MORPHOLOGY_FLASHCARDS_LAYERS,
    (),
    GroundingPolicy(True, "insufficient_evidence", True),
    StateWritePolicy(),
    (CapabilityRequirement("structured_output"),),
    (ToolRequirement("source.prepare_planned_flashcard_scope", VERSION),),
    ArtifactReference("propose_flashcards_morphology_flow", VERSION),
    fallbacks=(
        CapabilityFallback(
            "structured_output",
            "parse_json_then_validate",
            validator_ids=("morphology_flashcards_integrity",),
        ),
    ),
    validators=(
        ValidatorDefinition(
            "morphology_flashcards_readiness", VERSION, "Require sufficient planned evidence."
        ),
        ValidatorDefinition(
            "morphology_flashcards_integrity",
            VERSION,
            "Validate coverage, morphology roles, hierarchy and grounding.",
        ),
    ),
    known_failure_modes=(
        "profile selection lacks trusted anatomy provenance",
        "object plan does not cover the active bundle exactly once",
        "atomic discrimination is not parented to its macro",
        "candidate evidence or verified media changed",
    ),
)

__all__ = ["MORPHOLOGY_FLASHCARDS_MODEL_SCHEMA", "MORPHOLOGY_FLASHCARDS_SKILL", "VERSION"]
