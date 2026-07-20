"""One-model, read-only free-response grading playbook."""

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
from study_agent.prompts.grade_response_v1 import GRADE_RESPONSE_PROMPT
from study_agent.skills import (
    ArtifactReference,
    CapabilityRequirement,
    SemanticVersion,
    VersionRange,
)
from study_agent.skills.builtin.grade_response import GRADE_RESPONSE_MODEL_SCHEMA

VERSION = SemanticVersion.parse("1.0.0")


def _run(key: str) -> DataReference:
    return DataReference(DataSourceKind.RUN_INPUT, key)


def _output(key: str, *path: str) -> DataReference:
    return DataReference(DataSourceKind.STEP_OUTPUT, key, path)


GRADE_RESPONSE_FLOW = PlaybookDefinition(
    "grade_response_flow",
    VERSION,
    VersionRange(VERSION, SemanticVersion.parse("2.0.0")),
    (
        ToolStep(
            "prepare_grade_scope",
            ArtifactReference("assessment.prepare_grade_scope", VERSION),
            {},
            "prepared_grade",
            (
                DataBinding("attempt_id", _run("attempt_id")),
                DataBinding("language", _run("language")),
            ),
        ),
        ValidateStep(
            "check_grade_readiness",
            ArtifactReference("grade_response_readiness", VERSION),
            ("prepared_grade",),
            "readiness",
            (
                DataBinding("prepared_scope", _output("prepared_grade", "prepared_scope")),
                DataBinding(
                    "prompt_projection", _output("prepared_grade", "prompt_projection")
                ),
            ),
        ),
        ModelStep(
            "grade_free_response",
            GRADE_RESPONSE_PROMPT,
            ModelRequest(
                (ModelMessage(MessageRole.USER, "Grade the pinned immutable attempt scope."),),
                StructuredOutputConstraint(
                    "grade_response_criteria", GRADE_RESPONSE_MODEL_SCHEMA.value, True
                ),
                temperature=0,
            ),
            GRADE_RESPONSE_MODEL_SCHEMA,
            "draft",
            (CapabilityRequirement("structured_output"),),
            (
                DataBinding("language", _run("language")),
                DataBinding("response", _output("prepared_grade", "prompt_projection", "response")),
                DataBinding(
                    "expected_response",
                    _output("prepared_grade", "prompt_projection", "expected_response"),
                ),
                DataBinding("rubric", _output("prepared_grade", "prompt_projection", "rubric")),
                DataBinding(
                    "evidence", _output("prepared_grade", "prompt_projection", "evidence")
                ),
            ),
        ),
        ValidateStep(
            "validate_grade",
            ArtifactReference("grade_response_integrity", VERSION),
            ("prepared_grade", "draft"),
            "grade",
            (
                DataBinding("prepared_scope", _output("prepared_grade", "prepared_scope")),
            ),
        ),
    ),
    ("attempt_id", "language"),
)

__all__ = ["GRADE_RESPONSE_FLOW", "VERSION"]
