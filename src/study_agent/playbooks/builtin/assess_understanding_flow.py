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
from study_agent.prompts import ASSESS_UNDERSTANDING_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    JsonSchema,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin import ASSESS_UNDERSTANDING_MODEL_SCHEMA

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

ASSESS_UNDERSTANDING_FLOW = PlaybookDefinition(
    "assess_understanding_flow",
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
            ArtifactReference("assess_understanding_readiness", VERSION),
            ("evidence_gate",),
            "readiness",
            (
                DataBinding("scope", _run("scope")),
                DataBinding("assessment_format", _run("assessment_format")),
            ),
        ),
        DialogueStep(
            "clarify_scope",
            "Which scope should these questions assess?",
            CLARIFICATION_SCHEMA,
            "clarification",
            DialogueGate(
                _output("readiness", "needs_clarification"),
                {"provided": False, "text": ""},
            ),
        ),
        ModelStep(
            "generate_questions",
            ASSESS_UNDERSTANDING_PROMPT,
            ModelRequest(
                (
                    ModelMessage(
                        MessageRole.USER,
                        "Compose the pinned assessment prompt before execution.",
                    ),
                ),
                StructuredOutputConstraint(
                    "assessment_questions_draft",
                    ASSESS_UNDERSTANDING_MODEL_SCHEMA.value,
                    True,
                ),
                temperature=0,
            ),
            ASSESS_UNDERSTANDING_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("query", _run("query")),
                DataBinding("scope", _run("scope")),
                DataBinding("question_count", _run("question_count")),
                DataBinding("language", _run("language")),
                DataBinding(
                    "assessment_format",
                    _output("readiness", "effective_assessment_format"),
                ),
                DataBinding(
                    "continuation_summary_json",
                    _run("continuation_summary_json"),
                ),
                DataBinding("clarification", _output("clarification")),
                DataBinding("evidence", _output("evidence")),
            ),
        ),
        ValidateStep(
            "validate_questions",
            ArtifactReference("assess_understanding_integrity", VERSION),
            ("evidence",),
            "assessment",
            (
                DataBinding("questions", _output("draft")),
                DataBinding("question_count", _run("question_count")),
            ),
        ),
    ),
    (
        "query",
        "scope",
        "assessment_format",
        "question_count",
        "language",
        "continuation_summary_json",
    ),
)
