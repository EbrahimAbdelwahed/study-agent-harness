from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import (
    Actor,
    AnswerId,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    InteractionId,
    InteractionKind,
    PrincipalKind,
    SessionId,
    SessionStatus,
)
from study_agent.ports import AnswerNotFoundError, SessionViewPort
from study_agent.sessions import (
    SESSION_INTERACTION_RECORDED,
    SESSION_STARTED,
    ProjectionSessionView,
    interaction_recorded_payload,
    register_session_events,
    session_started_payload,
)
from study_agent.state import EventRegistry, Projection, apply_event


def _event(sequence: int, event_type: str, payload: object) -> DomainEvent:
    return DomainEvent(
        EventId(f"event-{sequence}"),
        CourseId("course"),
        sequence,
        event_type,
        1,
        Actor(PrincipalKind.HUMAN, "learner"),
        datetime(2026, 7, 11, tzinfo=UTC) + timedelta(seconds=sequence),
        CorrelationId("correlation"),
        payload,  # type: ignore[arg-type]
        SessionId("session"),
    )


def test_projection_session_view_satisfies_port_without_mutation_or_storage_types() -> None:
    registry = EventRegistry()
    register_session_events(registry)
    projection = Projection(CourseId("course"))
    projection = apply_event(
        projection,
        _event(1, SESSION_STARTED, session_started_payload(SessionId("session"))),
        registry,
    )
    projection = apply_event(
        projection,
        _event(
            2,
            SESSION_INTERACTION_RECORDED,
            interaction_recorded_payload(
                InteractionId("note"), InteractionKind.NOTE, "Review this later"
            ),
        ),
        registry,
    )
    view: SessionViewPort = ProjectionSessionView(lambda _: projection)

    session = view.get_session(CourseId("course"), SessionId("session"))
    assert session.status is SessionStatus.ACTIVE
    assert session.interaction_ids == (InteractionId("note"),)
    assert view.interactions(CourseId("course"), SessionId("session"))[0].content == (
        "Review this later"
    )
    assert view.answers(CourseId("course"), SessionId("session")) == ()
    assert view.get_context(CourseId("course"), SessionId("session")) is None
    with pytest.raises(AnswerNotFoundError):
        view.get_answer(CourseId("course"), SessionId("session"), AnswerId("missing"))


def test_view_rejects_loader_returning_another_course() -> None:
    view = ProjectionSessionView(lambda _: Projection(CourseId("other")))
    with pytest.raises(ValueError, match="another course"):
        view.get_session(CourseId("course"), SessionId("session"))
