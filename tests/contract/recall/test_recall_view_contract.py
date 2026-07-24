from __future__ import annotations

from study_agent.domain import CourseId
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
