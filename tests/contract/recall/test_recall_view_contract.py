from __future__ import annotations

import pytest

from study_agent.domain import CourseId
from study_agent.domain._validation import JsonValue
from study_agent.recall.contracts import RecallSnapshot
from study_agent.recall.view import ProjectionRecallView
from study_agent.state import Projection


def test_projection_recall_view_is_read_only_and_high_water_marked() -> None:
    course = CourseId("course-1")
    projection = Projection(
        course, 12, {"recall": {"enrollments": {}, "reviews": {}, "schedules": {}, "commands": {}}}
    )
    view = ProjectionRecallView(
        lambda requested: projection if requested == course else Projection(requested)
    )
    snapshot = view.get(course)
    assert isinstance(snapshot, RecallSnapshot)
    assert snapshot.course_id == course
    assert snapshot.sequence == 12
    assert snapshot.reviews == ()
    assert snapshot.schedules == ()
    assert projection.state == {
        "recall": {"enrollments": {}, "reviews": {}, "schedules": {}, "commands": {}}
    }


def test_projection_recall_view_rejects_missing_or_opaque_sections() -> None:
    course = CourseId("course-1")
    recalls: tuple[dict[str, JsonValue], ...] = (
        {"enrollments": {}, "reviews": {}, "schedules": {}},
        {
            "enrollments": {},
            "reviews": {},
            "schedules": {},
            "commands": {},
            "opaque_package_state": {},
        },
    )
    for recall in recalls:
        with pytest.raises(ValueError, match="projection fields"):
            projection = Projection(course, 1, {"recall": recall})

            def load(_: CourseId, projection: Projection = projection) -> Projection:
                return projection

            ProjectionRecallView(load).get(course)
