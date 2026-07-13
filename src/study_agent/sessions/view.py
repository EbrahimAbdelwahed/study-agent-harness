"""Storage-neutral reference reader over immutable course projections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import cast

from study_agent.domain._validation import JsonValue
from study_agent.domain.identifiers import AnswerId, CourseId, InteractionId, RunId, SessionId
from study_agent.domain.session import (
    AnswerRecord,
    ContinuationSummaryV1,
    InteractionRecord,
    SessionStatus,
    StudySessionRecord,
)
from study_agent.ports.session import AnswerNotFoundError, SessionNotFoundError
from study_agent.state import Projection

from .events import decode_summary_manifest
from .projection import _decode_answer, _decode_interaction

type ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionSessionView:
    """Read session records from a projection supplied by the composition root."""

    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def list_sessions(self, course_id: CourseId) -> tuple[StudySessionRecord, ...]:
        """Enumerate one course's projected sessions without mutable catalog state."""
        projection = self._projection(course_id)
        sessions = _mapping(projection.state.get("sessions", {}), "sessions")
        result: list[StudySessionRecord] = []
        for session_id, raw in sessions.items():
            if not isinstance(session_id, str) or not session_id or not isinstance(raw, Mapping):
                raise ValueError("session projection entry is corrupt")
            result.append(self._decode_session(course_id, SessionId(session_id), raw))
        return tuple(sorted(result, key=lambda item: (item.started_at, str(item.id))))

    def get_session(self, course_id: CourseId, session_id: SessionId) -> StudySessionRecord:
        projection = self._projection(course_id)
        sessions = _mapping(projection.state.get("sessions", {}), "sessions")
        raw = sessions.get(str(session_id))
        return self._decode_session(course_id, session_id, raw)

    @staticmethod
    def _decode_session(
        course_id: CourseId, session_id: SessionId, raw: JsonValue | None
    ) -> StudySessionRecord:
        if not isinstance(raw, Mapping):
            raise SessionNotFoundError(course_id, session_id)
        if raw.get("course_id") != str(course_id) or raw.get("session_id") != str(session_id):
            raise ValueError("session projection ownership is corrupt")
        expected = {
            "session_id",
            "course_id",
            "status",
            "started_at",
            "suspended_at",
            "resumed_at",
            "ended_at",
            "last_event_at",
            "interaction_ids",
            "run_ids",
            "continuation_summary",
        }
        if set(raw) != expected:
            raise ValueError("session projection fields are corrupt")
        interaction_ids = _string_array(raw.get("interaction_ids"), "interaction_ids")
        run_ids = _string_array(raw.get("run_ids"), "run_ids")
        summary_raw = raw.get("continuation_summary")
        summary = None if summary_raw is None else decode_summary_manifest(summary_raw)
        try:
            status = SessionStatus(_string(raw.get("status"), "status"))
        except ValueError as error:
            raise ValueError("session projection status is corrupt") from error
        started_at = _timestamp(raw.get("started_at"), "started_at", required=True)
        if started_at is None:  # pragma: no cover - guaranteed by required=True
            raise ValueError("session projection started_at is required")
        return StudySessionRecord(
            id=session_id,
            course_id=course_id,
            status=status,
            started_at=started_at,
            suspended_at=_timestamp(raw.get("suspended_at"), "suspended_at"),
            resumed_at=_timestamp(raw.get("resumed_at"), "resumed_at"),
            ended_at=_timestamp(raw.get("ended_at"), "ended_at"),
            interaction_ids=tuple(InteractionId(item) for item in interaction_ids),
            run_ids=tuple(RunId(item) for item in run_ids),
            continuation_summary=summary,
        )

    def interactions(
        self, course_id: CourseId, session_id: SessionId
    ) -> tuple[InteractionRecord, ...]:
        record = self.get_session(course_id, session_id)
        raw_interactions = _mapping(
            self._projection(course_id).state.get("session_interactions", {}),
            "session_interactions",
        )
        result: list[InteractionRecord] = []
        for interaction_id in record.interaction_ids:
            raw = raw_interactions.get(str(interaction_id))
            if not isinstance(raw, Mapping) or raw.get("session_id") != str(session_id):
                raise ValueError("session interaction linkage is corrupt")
            result.append(_decode_interaction(str(interaction_id), raw))
        return tuple(result)

    def answers(
        self, course_id: CourseId, session_id: SessionId
    ) -> tuple[AnswerRecord, ...]:
        record = self.get_session(course_id, session_id)
        run_order = {run_id: index for index, run_id in enumerate(record.run_ids)}
        raw_answers = _mapping(
            self._projection(course_id).state.get("session_answers", {}), "session_answers"
        )
        result: list[AnswerRecord] = []
        for answer_id, raw in raw_answers.items():
            if not isinstance(raw, Mapping):
                raise ValueError("answer projection is corrupt")
            if raw.get("session_id") == str(session_id):
                result.append(_decode_answer(answer_id, raw))
        if len(result) != len(record.run_ids):
            raise ValueError("session answer/run projection linkage is corrupt")
        result.sort(key=lambda item: run_order[item.run_id])
        return tuple(result)

    def get_answer(
        self, course_id: CourseId, session_id: SessionId, answer_id: AnswerId
    ) -> AnswerRecord:
        raw_answers = _mapping(
            self._projection(course_id).state.get("session_answers", {}), "session_answers"
        )
        raw = raw_answers.get(str(answer_id))
        if not isinstance(raw, Mapping) or raw.get("session_id") != str(session_id):
            raise AnswerNotFoundError(session_id, answer_id)
        return _decode_answer(str(answer_id), raw)

    def get_context(
        self, course_id: CourseId, session_id: SessionId
    ) -> ContinuationSummaryV1 | None:
        return self.get_session(course_id, session_id).continuation_summary

    def _projection(self, course_id: CourseId) -> Projection:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        return projection


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value


def _string(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"projection field {name} must be non-empty text")
    return value


def _string_array(value: JsonValue | None, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"projection field {name} must be an array of strings")
    return cast(tuple[str, ...], value)


def _timestamp(
    value: JsonValue | None, name: str, *, required: bool = False
) -> datetime | None:
    if value is None:
        if required:
            raise ValueError(f"projection field {name} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"projection field {name} must be an ISO timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"projection field {name} must be an ISO timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"projection field {name} must be timezone-aware")
    return result
