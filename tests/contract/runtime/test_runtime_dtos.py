from __future__ import annotations

from dataclasses import fields

import pytest

import study_agent.api.runtime as runtime
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.identifiers import CourseId


def test_runtime_facade_exports_exactly_the_approved_names() -> None:
    expected = (
        "ArtifactDecisionRequest",
        "AssessmentObservationRequest",
        "AsyncStudyAgentRuntime",
        "CapabilityResumeRequest",
        "CapabilityStartRequest",
        "CommitReceipt",
        "EventSchema",
        "EventUpcasterRegistry",
        "KernelModule",
        "KernelModuleRegistry",
        "ModuleRegistry",
        "RecallReviewRequest",
        "Registry",
        "RuntimeDependencies",
        "RuntimePolicyPort",
        "RuntimeSnapshot",
        "SyncStudyAgentRuntime",
        "create_runtime",
    )
    assert runtime.__all__ == expected
    assert [name for name in dir(runtime) if not name.startswith("_")] == list(expected)


@pytest.mark.parametrize(
    ("contract", "names"),
    (
        ("CapabilityStartRequest", ("course_id", "session_id", "capability")),
        (
            "CapabilityResumeRequest",
            (
                "course_id",
                "session_id",
                "continuation",
                "response",
                "authority",
                "correlation_id",
                "expected_stream_high_water",
                "idempotency_key",
            ),
        ),
        (
            "ArtifactDecisionRequest",
            (
                "course_id",
                "session_id",
                "artifact_revision_id",
                "decision",
                "supersedes_revision_id",
                "authority",
                "correlation_id",
                "expected_stream_high_water",
                "idempotency_key",
            ),
        ),
        (
            "AssessmentObservationRequest",
            (
                "course_id",
                "session_id",
                "run_id",
                "supersedes_grade_id",
                "authority",
                "correlation_id",
                "expected_stream_high_water",
                "idempotency_key",
            ),
        ),
        (
            "RecallReviewRequest",
            (
                "course_id",
                "session_id",
                "revision_id",
                "rating",
                "authority",
                "correlation_id",
                "expected_stream_high_water",
                "idempotency_key",
                "latency_ms",
                "confidence_bps",
            ),
        ),
        (
            "RuntimeSnapshot",
            ("course_id", "stream_sequence", "state", "fingerprint"),
        ),
        (
            "CommitReceipt",
            (
                "operation",
                "course_id",
                "stream_sequence",
                "event_ids",
                "idempotency_key",
                "replayed",
                "result",
            ),
        ),
    ),
)
def test_runtime_dto_fields_are_frozen_and_exact(contract: str, names: tuple[str, ...]) -> None:
    dto = getattr(runtime, contract)
    assert tuple(field.name for field in fields(dto)) == names
    assert getattr(dto, "__dataclass_params__", None) is not None
    assert getattr(dto, "__slots__", None) is not None


def test_snapshot_freezes_json_and_rejects_invalid_bounds() -> None:
    state = {"nested": ("value",)}
    snapshot = runtime.RuntimeSnapshot(
        CourseId("course"),
        0,
        state,
        "0" * 64,
    )
    assert snapshot.state["nested"] == ("value",)
    with pytest.raises(TypeError):
        snapshot.state["new"] = "value"  # type: ignore[index]
    with pytest.raises(ValidationFailure):
        runtime.RuntimeSnapshot(CourseId("course"), -1, {}, "0" * 64)
    with pytest.raises(ValidationFailure):
        runtime.RuntimeSnapshot(CourseId("course"), 0, {}, "not-a-digest")


def test_dependencies_reject_missing_required_values() -> None:
    with pytest.raises(ValidationFailure, match="principal is required"):
        runtime.RuntimeDependencies(None, None, None, None, None, None, None)  # type: ignore[arg-type]
