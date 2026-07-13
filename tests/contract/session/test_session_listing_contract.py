from __future__ import annotations

import pytest

from study_agent.domain import CourseId, SessionId, SessionStatus
from study_agent.domain._validation import JsonValue
from study_agent.sessions import ProjectionSessionView
from study_agent.state import Projection


def _session(session_id: str, course_id: str, started_at: str) -> dict[str, JsonValue]:
    return {
        "session_id": session_id,
        "course_id": course_id,
        "status": "active",
        "started_at": started_at,
        "suspended_at": None,
        "resumed_at": None,
        "ended_at": None,
        "last_event_at": started_at,
        "interaction_ids": (),
        "run_ids": (),
        "continuation_summary": None,
    }


def test_listing_empty_projection_is_a_successful_empty_result() -> None:
    course_id = CourseId("course")
    view = ProjectionSessionView(lambda _: Projection(course_id))

    assert view.list_sessions(course_id) == ()


def test_listing_is_chronological_with_stable_identity_tiebreaker() -> None:
    course_id = CourseId("course")
    projection = Projection(
        course_id,
        state={
            "sessions": {
                "z-later": _session("z-later", "course", "2026-07-12T11:00:00Z"),
                "z-same": _session("z-same", "course", "2026-07-12T10:00:00Z"),
                "a-same": _session("a-same", "course", "2026-07-12T10:00:00Z"),
            }
        },
    )
    view = ProjectionSessionView(lambda _: projection)

    records = view.list_sessions(course_id)

    assert tuple(record.id for record in records) == (
        SessionId("a-same"),
        SessionId("z-same"),
        SessionId("z-later"),
    )
    assert all(record.course_id == course_id for record in records)
    assert all(record.status is SessionStatus.ACTIVE for record in records)


def test_listing_rejects_a_foreign_course_session_in_projection() -> None:
    course_id = CourseId("course")
    projection = Projection(
        course_id,
        state={
            "sessions": {
                "foreign": _session("foreign", "other-course", "2026-07-12T10:00:00Z")
            }
        },
    )
    view = ProjectionSessionView(lambda _: projection)

    try:
        view.list_sessions(course_id)
    except ValueError as error:
        assert str(error) == "session projection ownership is corrupt"
    else:  # pragma: no cover - assertion branch
        raise AssertionError("foreign course session was disclosed")


@pytest.mark.parametrize("malformed", [None, "bad", ()])
def test_listing_classifies_present_malformed_entry_as_corruption(
    malformed: JsonValue,
) -> None:
    course_id = CourseId("course")
    projection = Projection(course_id, state={"sessions": {"present": malformed}})
    view = ProjectionSessionView(lambda _: projection)

    with pytest.raises(ValueError, match="entry is corrupt"):
        view.list_sessions(course_id)


def test_get_still_classifies_an_absent_identity_as_not_found() -> None:
    course_id = CourseId("course")
    view = ProjectionSessionView(lambda _: Projection(course_id))

    from study_agent.ports import SessionNotFoundError

    with pytest.raises(SessionNotFoundError):
        view.get_session(course_id, SessionId("absent"))
