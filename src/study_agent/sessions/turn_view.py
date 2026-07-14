"""Projection-backed reader for canonical general assistant turns."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from study_agent.domain import (
    AssistantTurnRecord,
    AssistantTurnStatus,
    CourseId,
    EventId,
    InteractionId,
    RunId,
    SessionId,
    VerifiedRunOutputRef,
)
from study_agent.domain._validation import JsonValue
from study_agent.ports import SessionNotFoundError
from study_agent.state import Projection

type ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionAssistantTurnView:
    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def turns(
        self, course_id: CourseId, session_id: SessionId
    ) -> tuple[AssistantTurnRecord, ...]:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        sessions = _mapping(projection.state.get("sessions", {}), "sessions")
        session = sessions.get(str(session_id))
        if session is None:
            raise SessionNotFoundError(course_id, session_id)
        if (
            not isinstance(session, Mapping)
            or session.get("session_id") != str(session_id)
            or session.get("course_id") != str(course_id)
        ):
            raise ValueError("session projection ownership is corrupt")
        interactions = _mapping(
            projection.state.get("session_interactions", {}),
            "session_interactions",
        )
        raw_turns = _mapping(
            projection.state.get("session_assistant_turns", {}),
            "session_assistant_turns",
        )
        decoded = tuple(_decode_turn(turn_id, raw) for turn_id, raw in raw_turns.items())
        for item in decoded:
            owner = sessions.get(str(item.session_id))
            if (
                not isinstance(owner, Mapping)
                or owner.get("session_id") != str(item.session_id)
                or owner.get("course_id") != str(course_id)
            ):
                raise ValueError("assistant turn projection ownership is corrupt")
            if item.in_reply_to_interaction_id is not None:
                reply = interactions.get(str(item.in_reply_to_interaction_id))
                if (
                    not isinstance(reply, Mapping)
                    or reply.get("session_id") != str(item.session_id)
                    or reply.get("kind") != "human"
                ):
                    raise ValueError("assistant turn projection reply linkage is corrupt")
        result = tuple(item for item in decoded if item.session_id == session_id)
        return tuple(sorted(result, key=lambda item: item.course_sequence))


def _decode_turn(turn_id: object, raw: JsonValue) -> AssistantTurnRecord:
    if not isinstance(turn_id, str) or not isinstance(raw, Mapping):
        raise ValueError("assistant turn projection entry is corrupt")
    expected = {
        "session_id",
        "status",
        "content",
        "in_reply_to_interaction_id",
        "run_id",
        "output_key",
        "output_fingerprint",
        "idempotency_key",
        "command_fingerprint",
        "event_id",
        "course_sequence",
        "occurred_at",
    }
    if set(raw) != expected:
        raise ValueError("assistant turn projection fields are corrupt")
    reply_raw = raw.get("in_reply_to_interaction_id")
    if reply_raw is not None and not isinstance(reply_raw, str):
        raise ValueError("assistant turn reply linkage is corrupt")
    sequence = raw.get("course_sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError("assistant turn sequence is corrupt")
    try:
        occurred_at = datetime.fromisoformat(_text(raw, "occurred_at").replace("Z", "+00:00"))
        status = AssistantTurnStatus(_text(raw, "status"))
    except ValueError as error:
        raise ValueError("assistant turn projection is corrupt") from error
    return AssistantTurnRecord(
        id=InteractionId(turn_id),
        session_id=SessionId(_text(raw, "session_id")),
        occurred_at=occurred_at,
        status=status,
        content=_text(raw, "content"),
        in_reply_to_interaction_id=(
            InteractionId(reply_raw) if isinstance(reply_raw, str) else None
        ),
        output=VerifiedRunOutputRef(
            run_id=RunId(_text(raw, "run_id")),
            output_key=_text(raw, "output_key"),
            output_fingerprint=_text(raw, "output_fingerprint"),
        ),
        idempotency_key=_text(raw, "idempotency_key"),
        command_fingerprint=_text(raw, "command_fingerprint"),
        event_id=EventId(_text(raw, "event_id")),
        course_sequence=sequence,
    )


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value


def _text(value: Mapping[str, JsonValue], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise ValueError(f"assistant turn {name} is corrupt")
    return result
