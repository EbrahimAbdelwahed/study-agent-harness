"""Projection-backed typed assessment views."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from study_agent.artifacts.content import AssessmentItemContent, StudyArtifactEnvelope
from study_agent.domain import (
    ArtifactRevisionId,
    AttemptId,
    CourseId,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    SessionId,
)
from study_agent.domain._validation import JsonValue
from study_agent.ports import CourseNotFoundError
from study_agent.state import Projection

from .contracts import (
    AssessmentSnapshot,
    AttemptRecord,
    GradeContestRecord,
    GradeRecord,
    PresentationRecord,
)
from .events import _criterion, _provenance, _response, _score

type ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionAssessmentView:
    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def get(self, course_id: CourseId) -> AssessmentSnapshot:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        if "course" not in projection.state:
            raise CourseNotFoundError(course_id)
        raw = projection.state.get("assessments", {})
        if not isinstance(raw, Mapping) or (
            raw and set(raw) != {"presentations", "attempts", "grades", "contests", "commands"}
        ):
            raise ValueError("assessment projection fields are corrupt")
        presentations_raw = _mapping(raw.get("presentations", {}), "presentations")
        attempts_raw = _mapping(raw.get("attempts", {}), "attempts")
        grades_raw = _mapping(raw.get("grades", {}), "grades")
        contests_raw = raw.get("contests", ())
        if not isinstance(contests_raw, tuple):
            raise ValueError("assessment contest history is corrupt")
        presentations = tuple(self._presentation(value) for value in presentations_raw.values())
        attempts = tuple(self._attempt(value) for value in attempts_raw.values())
        grades = tuple(self._grade(value) for value in grades_raw.values())
        contests = tuple(self._contest(value) for value in contests_raw)
        return AssessmentSnapshot(
            course_id,
            projection.sequence,
            presentations,
            attempts,
            grades,
            contests,
        )

    @staticmethod
    def _presentation(value: JsonValue) -> PresentationRecord:
        raw = _mapping(value, "presentation")
        envelope = StudyArtifactEnvelope.from_bytes(_text(raw, "content").encode())
        if not isinstance(envelope.content, AssessmentItemContent):
            raise ValueError("presentation content is not an assessment item")
        return PresentationRecord(
            PresentationId(_text(raw, "presentation_id")),
            CourseId(_text(raw, "course_id")),
            SessionId(_text(raw, "session_id")),
            ArtifactRevisionId(_text(raw, "revision_id")),
            _text(raw, "content_fingerprint"),
            envelope.content,
            _time(raw, "presented_at"),
        )

    @staticmethod
    def _attempt(value: JsonValue) -> AttemptRecord:
        raw = _mapping(value, "attempt")
        latency = raw.get("latency_ms")
        if latency is not None and type(latency) is not int:
            raise ValueError("attempt latency_ms is corrupt")
        return AttemptRecord(
            AttemptId(_text(raw, "attempt_id")),
            CourseId(_text(raw, "course_id")),
            SessionId(_text(raw, "session_id")),
            PresentationId(_text(raw, "presentation_id")),
            _response(raw.get("response")),
            _text(raw, "response_fingerprint"),
            latency,
            _time(raw, "recorded_at"),
        )

    @staticmethod
    def _grade(value: JsonValue) -> GradeRecord:
        raw = _mapping(value, "grade")
        criteria = _objects(raw, "criterion_results")
        supersedes = raw.get("supersedes_grade_id")
        if supersedes is not None and not isinstance(supersedes, str):
            raise ValueError("grade predecessor identity is corrupt")
        return GradeRecord(
            GradeId(_text(raw, "grade_id")),
            CourseId(_text(raw, "course_id")),
            SessionId(_text(raw, "session_id")),
            AttemptId(_text(raw, "attempt_id")),
            GradeStatus(_text(raw, "status")),
            tuple(_criterion(item) for item in criteria),
            _score(raw.get("score")),
            _provenance(raw.get("provenance")),
            GradeLifecycle(_text(raw, "lifecycle")),
            GradeId(supersedes) if isinstance(supersedes, str) else None,
            _time(raw, "recorded_at"),
        )

    @staticmethod
    def _contest(value: JsonValue) -> GradeContestRecord:
        raw = _mapping(value, "contest")
        return GradeContestRecord(
            GradeId(_text(raw, "grade_id")),
            CourseId(_text(raw, "course_id")),
            SessionId(_text(raw, "session_id")),
            _text(raw, "reason"),
            _time(raw, "contested_at"),
        )


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _objects(value: Mapping[str, JsonValue], key: str) -> tuple[Mapping[str, JsonValue], ...]:
    raw = value.get(key)
    if not isinstance(raw, tuple) or any(not isinstance(item, Mapping) for item in raw):
        raise ValueError(f"{key} must be an array of objects")
    return tuple(item for item in raw if isinstance(item, Mapping))


def _text(value: Mapping[str, JsonValue], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be text")
    return raw


def _time(value: Mapping[str, JsonValue], key: str) -> datetime:
    raw = _text(value, key)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{key} must be timezone-aware")
    return parsed


__all__ = ["ProjectionAssessmentView", "ProjectionLoader"]
