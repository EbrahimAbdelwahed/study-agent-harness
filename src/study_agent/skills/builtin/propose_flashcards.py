"""Public schemas for the profile-dispatched flashcard proposal capability."""

from __future__ import annotations

from study_agent.domain._validation import JsonObject
from study_agent.skills import JsonSchema

PROPOSE_FLASHCARDS_INPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": (
            "query",
            "scope",
            "language",
            "candidate_ceiling",
            "continuation_summary_json",
        ),
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "scope": {"type": ("string", "null")},
            "language": {"type": "string", "minLength": 1},
            "candidate_ceiling": {"type": "integer", "minimum": 1, "maximum": 24},
            "continuation_summary_json": {"type": ("string", "null")},
        },
    }
)

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
        "retrieval_form": {
            "type": "string",
            "enum": ("direct_recall", "contextual_gap"),
        },
        "prompt": {"type": "string", "minLength": 1},
        "answer_blocks": {
            "type": "array",
            "items": _ANSWER_BLOCK_SCHEMA,
            "minItems": 1,
            "maxItems": 8,
        },
        "pedagogical_role": {
            "type": "string",
            "enum": (
                "overview",
                "section",
                "detail",
                "macro_reconstruction",
                "atomic_discrimination",
            ),
        },
        "morphology_family": {
            "type": ("string", "null"),
            "enum": (
                None,
                "components",
                "topology",
                "relations",
                "course",
                "profiles",
                "landmarks",
            ),
        },
        "cognitive_function": {
            "type": ("string", "null"),
            "enum": (None, "reconstruct", "localize", "relate", "discriminate"),
        },
        "rationale": {"type": "string", "minLength": 1},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": 16,
        },
        "media_evidence_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "maxItems": 8,
        },
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

PROPOSE_FLASHCARDS_OUTPUT_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("candidates", "omissions"),
        "additionalProperties": False,
        "properties": {
            "candidates": {
                "type": "array",
                "items": _CANDIDATE_SCHEMA,
                "maxItems": 24,
            },
            "omissions": {
                "type": "array",
                "items": _OMISSION_SCHEMA,
                "maxItems": 24,
            },
        },
    }
)


__all__ = ["PROPOSE_FLASHCARDS_INPUT_SCHEMA", "PROPOSE_FLASHCARDS_OUTPUT_SCHEMA"]
