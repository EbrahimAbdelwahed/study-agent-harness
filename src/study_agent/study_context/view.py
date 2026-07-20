"""Projection-backed reader for progressive study context."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime

from study_agent.domain import (
    CourseId,
    EventId,
    InteractionId,
    SessionId,
    StatementId,
    StatementStatus,
    StudyContextConflict,
    StudyContextResolution,
    StudyContextSnapshot,
    StudyContextStatement,
    StudyStatementInput,
    StudyStatementKind,
)
from study_agent.domain._validation import JsonValue
from study_agent.ports import CourseNotFoundError
from study_agent.state import Projection

type ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionStudyContextView:
    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def get(self, course_id: CourseId) -> StudyContextSnapshot:
        projection = self._projection(course_id)
        raw = projection.state.get("study_context", {})
        if not isinstance(raw, Mapping):
            raise ValueError("study-context projection is corrupt")
        if raw and set(raw) != {"statements", "resolutions", "commands"}:
            raise ValueError("study-context projection fields are corrupt")
        statements_raw = raw.get("statements", {})
        resolutions_raw = raw.get("resolutions", ())
        if not isinstance(statements_raw, Mapping) or not isinstance(resolutions_raw, tuple):
            raise ValueError("study-context projection collections are corrupt")
        statements = tuple(
            self._statement(course_id, key, value)
            for key, value in statements_raw.items()
        )
        statements = tuple(sorted(statements, key=lambda item: (item.recorded_at, str(item.id))))
        resolutions = tuple(self._resolution(value) for value in resolutions_raw)
        statements_by_id = {item.id: item for item in statements}
        for resolution in resolutions:
            selected = statements_by_id.get(resolution.selected_statement_id)
            losers = tuple(
                statements_by_id.get(statement_id)
                for statement_id in resolution.superseded_statement_ids
            )
            if (
                selected is None
                or selected.kind is not resolution.kind
                or any(
                    item is None
                    or item.kind is not resolution.kind
                    or item.status is not StatementStatus.SUPERSEDED
                    for item in losers
                )
            ):
                raise ValueError("study-context resolution linkage is corrupt")
        conflicts: list[StudyContextConflict] = []
        for kind in (StudyStatementKind.DEADLINE, StudyStatementKind.WEEKLY_TIME_BUDGET):
            active = tuple(
                item
                for item in statements
                if item.kind is kind and item.status is StatementStatus.ACTIVE
            )
            if len({_value_key(item.value) for item in active}) > 1:
                conflicts.append(StudyContextConflict(kind, tuple(item.id for item in active)))
        return StudyContextSnapshot(
            course_id,
            projection.sequence,
            statements,
            resolutions,
            tuple(conflicts),
        )

    def command_fingerprint(self, course_id: CourseId, event_id: EventId) -> str | None:
        projection = self._projection(course_id)
        context = projection.state.get("study_context", {})
        if not isinstance(context, Mapping):
            raise ValueError("study-context projection is corrupt")
        commands = context.get("commands", {})
        if not isinstance(commands, Mapping):
            raise ValueError("study-context command projection is corrupt")
        raw = commands.get(str(event_id))
        if raw is None:
            return None
        if not isinstance(raw, Mapping) or set(raw) != {
            "command_fingerprint",
            "statement_id",
        }:
            raise ValueError("study-context command entry is corrupt")
        fingerprint = raw.get("command_fingerprint")
        statement_id = raw.get("statement_id")
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in fingerprint)
            or not isinstance(statement_id, str)
            or not statement_id
        ):
            raise ValueError("study-context command fingerprint is corrupt")
        return fingerprint

    def _projection(self, course_id: CourseId) -> Projection:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        if "course" not in projection.state:
            raise CourseNotFoundError(course_id)
        return projection

    @staticmethod
    def _statement(
        course_id: CourseId, statement_id: object, raw: JsonValue
    ) -> StudyContextStatement:
        if not isinstance(statement_id, str) or not isinstance(raw, Mapping):
            raise ValueError("study-context statement entry is corrupt")
        expected = {
            "statement_id",
            "course_id",
            "session_id",
            "origin_interaction_id",
            "kind",
            "value",
            "status",
            "recorded_at",
        }
        if set(raw) != expected or raw.get("statement_id") != statement_id:
            raise ValueError("study-context statement fields are corrupt")
        if raw.get("course_id") != str(course_id):
            raise ValueError("study-context statement ownership is corrupt")
        kind = StudyStatementKind(_text(raw.get("kind"), "kind"))
        value: str | date | int
        if kind is StudyStatementKind.DEADLINE:
            value = date.fromisoformat(_text(raw.get("value"), "value"))
        else:
            candidate = raw.get("value")
            if not isinstance(candidate, (str, int)) or isinstance(candidate, bool):
                raise ValueError("study-context statement value is corrupt")
            value = candidate
        canonical = StudyStatementInput(kind, value)
        return StudyContextStatement(
            StatementId(statement_id),
            course_id,
            SessionId(_text(raw.get("session_id"), "session_id")),
            InteractionId(
                _text(raw.get("origin_interaction_id"), "origin_interaction_id")
            ),
            kind,
            canonical.value,
            StatementStatus(_text(raw.get("status"), "status")),
            _timestamp(raw.get("recorded_at"), "recorded_at"),
        )

    @staticmethod
    def _resolution(raw: JsonValue) -> StudyContextResolution:
        if not isinstance(raw, Mapping):
            raise ValueError("study-context resolution entry is corrupt")
        expected = {
            "event_id",
            "kind",
            "selected_statement_id",
            "superseded_statement_ids",
            "resolved_at",
        }
        raw_superseded = raw.get("superseded_statement_ids")
        if set(raw) != expected or not isinstance(raw_superseded, tuple):
            raise ValueError("study-context resolution fields are corrupt")
        return StudyContextResolution(
            EventId(_text(raw.get("event_id"), "event_id")),
            StudyStatementKind(_text(raw.get("kind"), "kind")),
            StatementId(
                _text(raw.get("selected_statement_id"), "selected_statement_id")
            ),
            tuple(
                StatementId(_text(item, "superseded_statement_id"))
                for item in raw_superseded
            ),
            _timestamp(raw.get("resolved_at"), "resolved_at"),
        )


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"projected {name} must be non-empty text")
    return value


def _timestamp(value: JsonValue | None, name: str) -> datetime:
    text = _text(value, name)
    result = datetime.fromisoformat(text)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"projected {name} must be timezone-aware")
    return result


def _value_key(value: str | date | int) -> tuple[str, str]:
    return type(value).__name__, value.isoformat() if isinstance(value, date) else str(value)
