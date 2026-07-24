from __future__ import annotations

from datetime import UTC, datetime

from study_agent.domain import CourseId
from study_agent.recall.view import ProjectionRecallView
from study_agent.state import Projection


def test_recall_view_rebuild_is_byte_identical_for_same_projection() -> None:
    course = CourseId("course-1")
    state = {
        "recall": {
            "enrollments": {},
            "reviews": {},
            "schedules": {},
            "commands": {},
        },
        "course": {"course_id": str(course)},
        "checked_at": datetime(2026, 7, 24, tzinfo=UTC).isoformat(),
    }
    projection = Projection(course, 4, state)
    first = ProjectionRecallView(lambda _: projection).get(course)
    second = ProjectionRecallView(lambda _: projection).get(course)
    assert first == second
    assert projection.canonical_bytes() == projection.canonical_bytes()
