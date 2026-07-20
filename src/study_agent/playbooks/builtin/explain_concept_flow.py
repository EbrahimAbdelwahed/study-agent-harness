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
from study_agent.ports import (
    MessageRole,
    ModelMessage,
    ModelRequest,
    StructuredOutputConstraint,
)
from study_agent.prompts import EXPLAIN_CONCEPT_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    JsonSchema,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin import EXPLAIN_CONCEPT_MODEL_SCHEMA

VERSION = SemanticVersion.parse("1.0.0")


def _run(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.RUN_INPUT, key, path)


def _output(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.STEP_OUTPUT, key, path)


CLARIFICATION_SCHEMA = JsonSchema(
    {
        "type": "object",
        "required": ("provided", "text"),
        "additionalProperties": False,
        "properties": {
            "provided": {"type": "boolean"},
            "text": {"type": "string"},
        },
    }
)

EXPLAIN_CONCEPT_FLOW = PlaybookDefinition(
    "explain_concept_flow",
    VERSION,
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    (
        ToolStep(
            "search_sources",
            ArtifactReference("source.search", VERSION),
            {},
            "evidence",
            (DataBinding("query", _run("query")),),
        ),
        ValidateStep(
            "check_evidence",
            ArtifactReference("tutor_evidence_gate", VERSION),
            ("evidence",),
            "evidence_gate",
        ),
        ValidateStep(
            "check_readiness",
            ArtifactReference("explain_concept_readiness", VERSION),
            ("evidence_gate",),
            "readiness",
            (DataBinding("target", _run("target")),),
        ),
        DialogueStep(
            "clarify_target",
            "Which concept or aspect should the explanation target?",
            CLARIFICATION_SCHEMA,
            "clarification",
            DialogueGate(
                _output("readiness", "needs_clarification"),
                {"provided": False, "text": ""},
            ),
        ),
        ModelStep(
            "generate_explanation",
            EXPLAIN_CONCEPT_PROMPT,
            ModelRequest(
                (
                    ModelMessage(
                        MessageRole.USER,
                        "Compose the pinned explanation prompt before execution.",
                    ),
                ),
                StructuredOutputConstraint(
                    "explain_concept_draft",
                    EXPLAIN_CONCEPT_MODEL_SCHEMA.value,
                    True,
                ),
                temperature=0,
            ),
            EXPLAIN_CONCEPT_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("query", _run("query")),
                DataBinding("target", _run("target")),
                DataBinding("language", _run("language")),
                DataBinding("learner_goal", _run("learner_goal")),
                DataBinding(
                    "continuation_summary_json",
                    _run("continuation_summary_json"),
                ),
                DataBinding("clarification", _output("clarification")),
                DataBinding("evidence", _output("evidence")),
            ),
        ),
        ValidateStep(
            "validate_explanation",
            ArtifactReference("explain_concept_integrity", VERSION),
            ("evidence",),
            "explanation",
            (DataBinding("answer", _output("draft")),),
        ),
    ),
    (
        "query",
        "target",
        "language",
        "learner_goal",
        "continuation_summary_json",
    ),
)
