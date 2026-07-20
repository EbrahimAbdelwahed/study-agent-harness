"""Private playbook for the hybrid macro-detail flashcard profile."""

from __future__ import annotations

from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    DialogueGate,
    DialogueStep,
    ModelStep,
    PlaybookDefinition,
    ToolStep,
    ValidateStep,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest, StructuredOutputConstraint
from study_agent.prompts.hybrid_flashcards_v1 import HYBRID_FLASHCARDS_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    JsonSchema,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin.hybrid_flashcards import HYBRID_FLASHCARDS_MODEL_SCHEMA

VERSION = SemanticVersion.parse("1.0.0")


def _run(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.RUN_INPUT, key, path)


def _output(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.STEP_OUTPUT, key, path)


HYBRID_FLASHCARDS_CLARIFICATION_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("provided", "text"),
        "additionalProperties": False,
        "properties": {"provided": {"type": "boolean"}, "text": {"type": "string"}},
    }
)

HYBRID_FLASHCARDS_FLOW = PlaybookDefinition(
    "propose_flashcards_hybrid_flow",
    VERSION,
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    (
        ToolStep(
            "prepare_planned_flashcard_scope",
            ArtifactReference("source.prepare_planned_flashcard_scope", VERSION),
            {},
            "prepared_scope",
            (DataBinding("query", _run("query")), DataBinding("scope", _run("scope"))),
        ),
        ValidateStep(
            "check_hybrid_readiness",
            ArtifactReference("hybrid_flashcards_readiness", VERSION),
            ("prepared_scope",),
            "readiness",
            (DataBinding("scope", _run("scope")),),
        ),
        DialogueStep(
            "clarify_hybrid_focus",
            "Which part of the prepared study scope should receive the strongest focus?",
            HYBRID_FLASHCARDS_CLARIFICATION_SCHEMA,
            "clarification",
            DialogueGate(
                _output("readiness", "needs_clarification"),
                {"provided": False, "text": ""},
            ),
        ),
        ModelStep(
            "generate_hybrid_flashcards",
            HYBRID_FLASHCARDS_PROMPT,
            ModelRequest(
                (
                    ModelMessage(
                        MessageRole.USER,
                        "Compose the pinned hybrid flashcard prompt before execution.",
                    ),
                ),
                StructuredOutputConstraint(
                    "hybrid_flashcards_draft",
                    HYBRID_FLASHCARDS_MODEL_SCHEMA.value,
                    True,
                ),
                temperature=0,
            ),
            HYBRID_FLASHCARDS_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("query", _run("query")),
                DataBinding("language", _run("language")),
                DataBinding("requested_ceiling", _run("candidate_ceiling")),
                DataBinding("continuation_summary_json", _run("continuation_summary_json")),
                DataBinding("clarification", _output("clarification")),
                DataBinding("prepared_scope", _output("prepared_scope")),
            ),
        ),
        ValidateStep(
            "validate_hybrid_flashcards",
            ArtifactReference("hybrid_flashcards_integrity", VERSION),
            ("prepared_scope", "draft"),
            "candidate_batch",
            (DataBinding("requested_ceiling", _run("candidate_ceiling")),),
        ),
    ),
    (
        "query",
        "scope",
        "language",
        "candidate_ceiling",
        "continuation_summary_json",
        "profile_selection_receipt",
    ),
)

__all__ = ["HYBRID_FLASHCARDS_CLARIFICATION_SCHEMA", "HYBRID_FLASHCARDS_FLOW", "VERSION"]
