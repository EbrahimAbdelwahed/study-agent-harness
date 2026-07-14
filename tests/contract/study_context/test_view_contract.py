from __future__ import annotations

import pytest

from study_agent.domain import CourseId, EventId
from study_agent.state import Projection
from study_agent.study_context import ProjectionStudyContextView

COURSE = CourseId("course-context-view")


def test_existing_course_without_statements_has_an_empty_sequence_bound_view() -> None:
    projection = Projection(COURSE, 1, {"course": {"course_id": str(COURSE)}})
    view = ProjectionStudyContextView(lambda _: projection)

    snapshot = view.get(COURSE)

    assert snapshot.course_id == COURSE
    assert snapshot.sequence == 1
    assert snapshot.statements == ()
    assert snapshot.resolutions == ()
    assert snapshot.conflicts == ()


def test_command_lookup_rejects_a_malformed_projection_entry() -> None:
    projection = Projection(
        COURSE,
        2,
        {
            "course": {"course_id": str(COURSE)},
            "study_context": {
                "statements": {},
                "resolutions": (),
                "commands": {
                    "event-command": {
                        "command_fingerprint": "not-a-sha256",
                        "statement_id": "statement-command",
                    }
                },
            },
        },
    )
    view = ProjectionStudyContextView(lambda _: projection)

    with pytest.raises(ValueError, match="fingerprint is corrupt"):
        view.command_fingerprint(COURSE, EventId("event-command"))
