from __future__ import annotations

from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
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
from study_agent.prompts import GROUNDED_ANSWER_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin import GROUNDED_ANSWER_MODEL_SCHEMA

VERSION = SemanticVersion.parse("1.0.0")


def _run(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.RUN_INPUT, key, path)


def _output(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.STEP_OUTPUT, key, path)


GROUNDED_ANSWER_FLOW = PlaybookDefinition(
    "grounded_answer_flow",
    VERSION,
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    (
        ToolStep(
            "load_context",
            ArtifactReference("session.get_context", VERSION),
            {},
            "context",
        ),
        ToolStep(
            "search_sources",
            ArtifactReference("source.search", VERSION),
            {},
            "evidence",
            (DataBinding("query", _run("question")),),
        ),
        ValidateStep(
            "check_evidence",
            ArtifactReference("evidence_sufficiency", VERSION),
            ("evidence",),
            "evidence_gate",
        ),
        ModelStep(
            "generate_answer",
            GROUNDED_ANSWER_PROMPT,
            ModelRequest(
                (ModelMessage(MessageRole.USER, "Compose the pinned prompt before execution."),),
                StructuredOutputConstraint(
                    "grounded_answer_draft",
                    GROUNDED_ANSWER_MODEL_SCHEMA.value,
                    True,
                ),
                temperature=0,
            ),
            GROUNDED_ANSWER_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("question", _run("question")),
                DataBinding("course_profile", _output("context", "course_profile")),
                DataBinding(
                    "continuation_summary",
                    _output("context", "continuation_summary"),
                ),
                DataBinding("evidence", _output("evidence")),
            ),
        ),
        ValidateStep(
            "validate_answer",
            ArtifactReference("grounded_answer_integrity", VERSION),
            ("evidence",),
            "validated_answer",
            (DataBinding("answer", _output("draft")),),
        ),
    ),
    ("course_id", "session_id", "question"),
)
