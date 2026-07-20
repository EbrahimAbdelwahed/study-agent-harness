"""Linear read-only playbook for exam-sample analysis."""

from study_agent.playbooks import (
    DataBinding,
    DataReference,
    DataSourceKind,
    ModelStep,
    PlaybookDefinition,
    ToolStep,
    ValidateStep,
)
from study_agent.ports import MessageRole, ModelMessage, ModelRequest, StructuredOutputConstraint
from study_agent.prompts.exam_sample_analysis_v1 import EXAM_SAMPLE_ANALYSIS_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin.analyze_exam_sample import EXAM_ANALYSIS_MODEL_SCHEMA

VERSION = SemanticVersion.parse("1.0.0")


def _run(key: str) -> DataReference:
    return DataReference(DataSourceKind.RUN_INPUT, key)


def _output(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.STEP_OUTPUT, key, path)


ANALYZE_EXAM_SAMPLE_FLOW = PlaybookDefinition(
    "analyze_exam_sample_flow",
    VERSION,
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    (
        ToolStep(
            "prepare_exam_sample_scope",
            ArtifactReference("source.prepare_exam_sample_scope", VERSION),
            {},
            "prepared_exam",
            (DataBinding("sample_revision_ids", _run("sample_revision_ids")),),
        ),
        ValidateStep(
            "check_exam_sample_readiness",
            ArtifactReference("exam_sample_readiness", VERSION),
            ("prepared_exam",),
            "readiness",
            (DataBinding("prepared_scope", _output("prepared_exam", "prepared_scope")),),
        ),
        ModelStep(
            "analyze_exam_samples",
            EXAM_SAMPLE_ANALYSIS_PROMPT,
            ModelRequest(
                (ModelMessage(MessageRole.USER, "Analyze the pinned redacted exam evidence."),),
                StructuredOutputConstraint(
                    "exam_analysis_draft", EXAM_ANALYSIS_MODEL_SCHEMA.value, True
                ),
                temperature=0,
            ),
            EXAM_ANALYSIS_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("language", _run("language")),
                DataBinding("prompt_projection", _output("prepared_exam", "prompt_projection")),
            ),
        ),
        ValidateStep(
            "validate_exam_blueprint",
            ArtifactReference("exam_blueprint_integrity", VERSION),
            ("prepared_exam", "draft"),
            "proposal",
            (DataBinding("prepared_scope", _output("prepared_exam", "prepared_scope")),),
        ),
    ),
    ("sample_revision_ids", "language"),
)

__all__ = ["ANALYZE_EXAM_SAMPLE_FLOW", "VERSION"]
