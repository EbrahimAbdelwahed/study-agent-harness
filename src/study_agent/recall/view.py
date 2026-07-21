"""Typed projection-only recall views."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from study_agent.domain import ArtifactRevisionId, CourseId, ReviewId, ScheduleDecisionId
from study_agent.domain._validation import JsonValue
from study_agent.state import Projection

from .contracts import AppliedSchedule, RecallSnapshot, RecallViewRow, RecallRating, ReviewRecord, SchedulingPolicyConfigV1

ProjectionLoader = Callable[[CourseId], Projection]


class ProjectionRecallView:
    def __init__(self, load_projection: ProjectionLoader) -> None:
        self._load_projection = load_projection

    def get(self, course_id: CourseId) -> RecallSnapshot:
        projection = self._load_projection(course_id)
        if projection.course_id != course_id:
            raise ValueError("projection loader returned another course")
        raw = projection.state.get("recall", {})
        if not isinstance(raw, Mapping):
            raise ValueError("recall projection is corrupt")
        enrollments_raw = _mapping(raw.get("enrollments", {}))
        reviews_raw = _mapping(raw.get("reviews", {}))
        schedules_raw = _mapping(raw.get("schedules", {}))
        enrollments = tuple(schedule_from_json(value) for value in enrollments_raw.values())
        reviews = tuple(review_record_from_json(value) for value in reviews_raw.values())
        schedules = tuple(schedule_from_json(value) for value in schedules_raw.values())
        return RecallSnapshot(course_id, projection.sequence, enrollments, reviews, schedules)

    def command_fingerprint(self, course_id: CourseId, event_id: str) -> str | None:
        raw = self._load_projection(course_id).state.get("recall", {})
        commands = _mapping(_mapping(raw).get("commands", {}))
        entry = commands.get(event_id)
        if entry is None:
            return None
        value = _mapping(entry)
        result = value.get("command_fingerprint")
        if not isinstance(result, str):
            raise ValueError("recall command fingerprint is corrupt")
        return result


def review_record_from_json(value: Mapping[str, JsonValue]) -> ReviewRecord:
    return ReviewRecord(
        ReviewId(_text(value.get("review_id"))), ArtifactRevisionId(_text(value.get("revision_id"))),
        RecallRating(_text(value.get("rating"))), _optional_int(value.get("latency_ms")),
        _optional_int(value.get("confidence_bps")), _time(value.get("occurred_at")),
        _text(value.get("idempotency_key")), _text(value.get("command_fingerprint")),
    )


def schedule_from_json(value: Mapping[str, JsonValue]) -> AppliedSchedule:
    policy_raw = _mapping(value.get("policy"))
    review = value.get("review_id")
    return AppliedSchedule(
        ScheduleDecisionId(_text(value.get("decision_id"))), ArtifactRevisionId(_text(value.get("revision_id"))),
        _text(value.get("trigger")), ReviewId(review) if isinstance(review, str) else None,
        _time(value.get("enrollment_at")), _time(value.get("due_at")), SchedulingPolicyConfigV1.from_json(policy_raw),
        _text(value.get("policy_id")), _text(value.get("policy_version")), _text(value.get("policy_fingerprint")),
        _text(value.get("implementation_id")), _text(value.get("implementation_version")),
        _text(value.get("history_fingerprint")), _text(value.get("result_fingerprint")),
        _text(value.get("idempotency_key")), _text(value.get("command_fingerprint")),
    )


def _mapping(value: object) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError("recall view object is corrupt")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("recall view text is corrupt")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError("recall view integer is corrupt")
    return value


def _time(value: object) -> datetime:
    text = _text(value)
    if not text.endswith("Z"):
        raise ValueError("recall view time must be UTC")
    return datetime.fromisoformat(text[:-1] + "+00:00").astimezone(UTC)


__all__ = ["ProjectionRecallView", "review_record_from_json", "schedule_from_json"]
