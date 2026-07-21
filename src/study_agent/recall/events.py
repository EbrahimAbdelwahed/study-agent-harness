"""Strict schema-v1 codecs for canonical recall events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    ReviewId,
    ScheduleDecisionId,
    SessionId,
    recall_event_id_for,
)
from study_agent.domain._validation import JsonObject, JsonValue, require_text

from .contracts import (
    AppliedSchedule,
    RecallRating,
    ReviewRecord,
    SchedulingPolicyConfigV1,
)

RECALL_SCHEMA_VERSION = 1
REVIEW_RECORDED = "recall.review_recorded"
SCHEDULE_APPLIED = "recall.schedule_applied"
RECALL_EVENT_TYPES = (REVIEW_RECORDED, SCHEDULE_APPLIED)


@dataclass(frozen=True, slots=True)
class ReviewRecorded:
    review: ReviewRecord


@dataclass(frozen=True, slots=True)
class ScheduleApplied:
    schedule: AppliedSchedule


def encode_review_recorded(
    record: ReviewRecord, *, course_id: CourseId, session_id: SessionId
) -> JsonObject:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("recall event scope is invalid")
    return {
        "course_id": str(course_id),
        "session_id": str(session_id),
        "review_id": str(record.review_id),
        "revision_id": str(record.revision_id),
        "rating": record.rating.value,
        "latency_ms": record.latency_ms,
        "confidence_bps": record.confidence_bps,
        "idempotency_key": record.idempotency_key,
        "command_fingerprint": record.command_fingerprint,
    }


def encode_schedule_applied(
    schedule: AppliedSchedule, *, course_id: CourseId, session_id: SessionId
) -> JsonObject:
    return {"course_id": str(course_id), "session_id": str(session_id), **schedule.to_json()}


def decode_review_recorded(event: DomainEvent) -> ReviewRecorded:
    payload = _event_payload(event, REVIEW_RECORDED, PrincipalKind.HUMAN)
    _strict(
        payload,
        {
            "course_id",
            "session_id",
            "review_id",
            "revision_id",
            "rating",
            "latency_ms",
            "confidence_bps",
            "idempotency_key",
            "command_fingerprint",
        },
    )
    key = _text(payload["idempotency_key"], "idempotency_key")
    if event.event_id != recall_event_id_for(
        event.course_id, cast(SessionId, event.session_id), key, REVIEW_RECORDED
    ):
        raise ValueError("review event identity does not match retry key")
    latency = _optional_int(payload["latency_ms"], "latency_ms")
    confidence = _optional_int(payload["confidence_bps"], "confidence_bps")
    if confidence is not None and confidence > 10000:
        raise ValueError("confidence_bps exceeds 10000")
    record = ReviewRecord(
        ReviewId(_text(payload["review_id"], "review_id")),
        ArtifactRevisionId(_text(payload["revision_id"], "revision_id")),
        RecallRating(_text(payload["rating"], "rating")),
        latency,
        confidence,
        event.occurred_at,
        key,
        _text(payload["command_fingerprint"], "command_fingerprint"),
    )
    return ReviewRecorded(record)


def decode_schedule_applied(event: DomainEvent) -> ScheduleApplied:
    payload = _event_payload(event, SCHEDULE_APPLIED, PrincipalKind.SERVICE)
    expected = {
        "course_id",
        "session_id",
        "decision_id",
        "revision_id",
        "trigger",
        "review_id",
        "enrollment_at",
        "due_at",
        "policy",
        "policy_id",
        "policy_version",
        "policy_fingerprint",
        "implementation_id",
        "implementation_version",
        "history_fingerprint",
        "result_fingerprint",
        "idempotency_key",
        "command_fingerprint",
    }
    _strict(payload, expected)
    key = _text(payload["idempotency_key"], "idempotency_key")
    if event.event_id != recall_event_id_for(
        event.course_id, cast(SessionId, event.session_id), key, SCHEDULE_APPLIED
    ):
        raise ValueError("schedule event identity does not match retry key")
    policy_raw = payload["policy"]
    if not isinstance(policy_raw, Mapping):
        raise ValueError("policy must be an object")
    policy = SchedulingPolicyConfigV1.from_json(policy_raw)
    review_raw = payload["review_id"]
    review_id = ReviewId(_text(review_raw, "review_id")) if isinstance(review_raw, str) else None
    schedule = AppliedSchedule(
        ScheduleDecisionId(_text(payload["decision_id"], "decision_id")),
        ArtifactRevisionId(_text(payload["revision_id"], "revision_id")),
        _text(payload["trigger"], "trigger"),
        review_id,
        _parse_time(payload["enrollment_at"], "enrollment_at"),
        _parse_time(payload["due_at"], "due_at"),
        policy,
        _text(payload["policy_id"], "policy_id"),
        _text(payload["policy_version"], "policy_version"),
        _text(payload["policy_fingerprint"], "policy_fingerprint"),
        _text(payload["implementation_id"], "implementation_id"),
        _text(payload["implementation_version"], "implementation_version"),
        _text(payload["history_fingerprint"], "history_fingerprint"),
        _text(payload["result_fingerprint"], "result_fingerprint"),
        key,
        _text(payload["command_fingerprint"], "command_fingerprint"),
    )
    return ScheduleApplied(schedule)


def decode_review_recorded_payload(payload: JsonObject, *, occurred_at: datetime) -> ReviewRecorded:
    event = DomainEvent(
        EventId("decode-placeholder"),
        CourseId(_text(payload.get("course_id"), "course_id")),
        1,
        REVIEW_RECORDED,
        1,
        Actor(PrincipalKind.HUMAN, "decoder"),
        occurred_at,
        CorrelationId("decode"),
        payload,
        SessionId(_text(payload.get("session_id"), "session_id")),
    )
    return decode_review_recorded(event)


def register_recall_events(registry: object) -> None:
    """Register exact decoders and pure reducers with a state EventRegistry."""
    from .projection import reduce_review_recorded, reduce_schedule_applied

    registry.register_event(  # type: ignore[attr-defined]
        REVIEW_RECORDED, RECALL_SCHEMA_VERSION, decode_review_recorded, reduce_review_recorded
    )
    registry.register_event(  # type: ignore[attr-defined]
        SCHEDULE_APPLIED, RECALL_SCHEMA_VERSION, decode_schedule_applied, reduce_schedule_applied
    )


def _event_payload(event: DomainEvent, event_type: str, authority: PrincipalKind) -> JsonObject:
    if event.event_type != event_type or event.schema_version != RECALL_SCHEMA_VERSION:
        raise ValueError(f"event envelope does not match {event_type}@1")
    if not isinstance(event.course_id, CourseId) or not isinstance(event.session_id, SessionId):
        raise ValueError("recall events must be course/session scoped")
    if not isinstance(event.actor, Actor) or event.actor.kind is not authority:
        raise ValueError(f"{event_type} requires {authority.value} authority")
    payload = event.payload
    if payload.get("course_id") != str(event.course_id) or payload.get("session_id") != str(
        event.session_id
    ):
        raise ValueError("recall event scope does not match envelope")
    return payload


def _strict(value: JsonObject, expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError("recall event payload fields are not exact")


def _text(value: JsonValue | object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    require_text(value, name)
    return value


def _optional_int(value: JsonValue | object, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or null")
    return value


def _parse_time(value: JsonValue | object, name: str) -> datetime:
    text = _text(value, name)
    if not text.endswith("Z"):
        raise ValueError(f"{name} must be normalized UTC")
    parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(UTC)


__all__ = [
    "RECALL_EVENT_TYPES",
    "RECALL_SCHEMA_VERSION",
    "REVIEW_RECORDED",
    "SCHEDULE_APPLIED",
    "ReviewRecorded",
    "ScheduleApplied",
    "decode_review_recorded",
    "decode_review_recorded_payload",
    "decode_schedule_applied",
    "encode_review_recorded",
    "encode_schedule_applied",
    "register_recall_events",
]
