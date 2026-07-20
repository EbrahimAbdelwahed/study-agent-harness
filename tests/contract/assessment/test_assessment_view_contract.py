from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest

from study_agent.artifacts import AssessmentItemContent, StudyArtifactEnvelope
from study_agent.assessments import ProjectionAssessmentView
from study_agent.domain import (
    ArtifactRevisionId,
    AssessmentFormat,
    CourseId,
    PresentationId,
    StudyArtifactKind,
)
from study_agent.ports import AssessmentViewPort, CourseNotFoundError
from study_agent.state import Projection


def _projection() -> Projection:
    content = AssessmentItemContent(
        AssessmentFormat.SINGLE_CHOICE,
        "Which structure?",
        ("A", "B"),
        "A",
        ("Names the correct structure",),
    )
    encoded = StudyArtifactEnvelope(StudyArtifactKind.ASSESSMENT_ITEM, content).to_bytes()
    return Projection(
        CourseId("course"),
        4,
        {
            "course": {"course_id": "course"},
            "assessments": {
                "presentations": {
                    "presentation": {
                        "presentation_id": "presentation",
                        "course_id": "course",
                        "session_id": "session",
                        "revision_id": "revision",
                        "content_fingerprint": sha256(encoded).hexdigest(),
                        "content": encoded.decode(),
                        "presented_at": datetime(2026, 7, 16, tzinfo=UTC)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                },
                "attempts": {},
                "grades": {},
                "contests": (),
                "commands": {},
            },
        },
    )


def test_projection_view_satisfies_port_and_redacts_hidden_assessment_material() -> None:
    projection = _projection()
    view: AssessmentViewPort = ProjectionAssessmentView(lambda _: projection)

    snapshot = view.get(CourseId("course"))
    learner = snapshot.learner_presentation(PresentationId("presentation"))

    assert snapshot.course_id == CourseId("course")
    assert snapshot.sequence == 4
    assert learner.presentation_id == PresentationId("presentation")
    assert learner.revision_id == ArtifactRevisionId("revision")
    assert learner.format is AssessmentFormat.SINGLE_CHOICE
    assert learner.prompt == "Which structure?"
    assert learner.options == ("A", "B")
    assert not hasattr(learner, "expected_response")
    assert not hasattr(learner, "evaluation_criteria")
    assert not hasattr(learner, "content_fingerprint")
    assert not hasattr(learner, "provenance")


def test_view_rejects_missing_course_wrong_course_and_unknown_presentation() -> None:
    with pytest.raises(CourseNotFoundError):
        ProjectionAssessmentView(lambda _: Projection(CourseId("course"))).get(CourseId("course"))
    with pytest.raises(ValueError, match="another course"):
        ProjectionAssessmentView(lambda _: _projection()).get(CourseId("other"))

    snapshot = ProjectionAssessmentView(lambda _: _projection()).get(CourseId("course"))
    with pytest.raises(LookupError, match="not found"):
        snapshot.learner_presentation(PresentationId("missing"))


def test_typed_snapshot_is_deterministic_and_does_not_mutate_projection() -> None:
    projection = _projection()
    before = projection.canonical_bytes()
    view = ProjectionAssessmentView(lambda _: projection)

    assert view.get(CourseId("course")) == view.get(CourseId("course"))
    assert projection.canonical_bytes() == before
