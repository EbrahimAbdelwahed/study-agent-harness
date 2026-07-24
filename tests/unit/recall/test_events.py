from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    ScheduleDecisionId,
    SessionId,
    recall_event_id_for,
    review_id_for,
)
from study_agent.recall.contracts import (
    AppliedSchedule,
    RecallRating,
    ReviewRecord,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    result_fingerprint,
)
from study_agent.recall.events import (
    REVIEW_RECORDED,
    SCHEDULE_APPLIED,
    decode_review_recorded,
    decode_review_recorded_payload,
    decode_schedule_applied,
    encode_review_recorded,
    encode_schedule_applied,
)

COURSE = CourseId("course-1")
SESSION = SessionId("session-1")
REVISION = ArtifactRevisionId("revision-1")
NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
POLICY = SchedulingPolicyConfigV1()
FP = "a" * 64


def _review() -> ReviewRecord:
    return ReviewRecord(
        review_id_for(COURSE, SESSION, REVISION, "review-key"),
        REVISION,
        RecallRating.GOOD,
        500,
        9000,
        NOW,
        "review-key",
        FP,
    )


def _event(
    *,
    event_id: EventId,
    event_type: str,
    payload: dict[str, object],
    actor: PrincipalKind,
    occurred_at: datetime = NOW,
) -> DomainEvent:
    return DomainEvent(
        event_id,
        COURSE,
        3,
        event_type,
        1,
        Actor(actor, "test"),
        occurred_at,
        CorrelationId("correlation-1"),
        payload,  # type: ignore[arg-type]
        SESSION,
    )


def _schedule() -> AppliedSchedule:
    review = _review()
    request = SchedulingRequest(REVISION, NOW, (review.history_entry(),), POLICY)
    partial = SchedulingResult(
        NOW + timedelta(days=1),
        "deterministic",
        "1",
        POLICY.fingerprint,
        "fake",
        "1",
        request.history_fingerprint,
        "0" * 64,
    )
    result = replace(partial, result_fingerprint=result_fingerprint(request, partial))
    return AppliedSchedule(
        ScheduleDecisionId("decision-1"),
        REVISION,
        "review",
        review.review_id,
        NOW,
        result.due_at,
        POLICY,
        result.policy_id,
        result.policy_version,
        result.policy_fingerprint,
        result.implementation_id,
        result.implementation_version,
        result.history_fingerprint,
        result.result_fingerprint,
        "schedule-key",
        FP,
    )


def test_review_codec_uses_trusted_event_time_and_exact_payload() -> None:
    record = _review()
    payload = encode_review_recorded(record, course_id=COURSE, session_id=SESSION)
    event_id = recall_event_id_for(COURSE, SESSION, record.idempotency_key, REVIEW_RECORDED)
    event = _event(
        event_id=event_id,
        event_type=REVIEW_RECORDED,
        payload=dict(payload),
        actor=PrincipalKind.HUMAN,
    )
    decoded = decode_review_recorded(event)
    assert decoded.review == record
    assert decode_review_recorded_payload(payload, occurred_at=NOW).review == record
    with pytest.raises(ValueError):
        decode_review_recorded(
            _event(
                event_id=event_id,
                event_type=REVIEW_RECORDED,
                payload={**payload, "extra": 1},
                actor=PrincipalKind.HUMAN,
            )
        )
    with pytest.raises(ValueError):
        decode_review_recorded(
            _event(
                event_id=event_id,
                event_type=REVIEW_RECORDED,
                payload=dict(payload),
                actor=PrincipalKind.SERVICE,
            )
        )
    changed_time = decode_review_recorded(
        _event(
            event_id=event_id,
            event_type=REVIEW_RECORDED,
            payload=dict(payload),
            actor=PrincipalKind.HUMAN,
            occurred_at=NOW + timedelta(hours=1),
        )
    )
    assert changed_time.review.occurred_at == NOW + timedelta(hours=1)


def test_schedule_codec_round_trips_and_rejects_wrong_scope_or_authority() -> None:
    schedule = _schedule()
    payload = encode_schedule_applied(schedule, course_id=COURSE, session_id=SESSION)
    event_id = recall_event_id_for(COURSE, SESSION, schedule.idempotency_key, SCHEDULE_APPLIED)
    event = _event(
        event_id=event_id,
        event_type=SCHEDULE_APPLIED,
        payload=dict(payload),
        actor=PrincipalKind.SERVICE,
    )
    assert decode_schedule_applied(event).schedule == schedule
    wrong_scope = {**payload, "course_id": "other-course"}
    with pytest.raises(ValueError):
        decode_schedule_applied(
            _event(
                event_id=event_id,
                event_type=SCHEDULE_APPLIED,
                payload=wrong_scope,
                actor=PrincipalKind.SERVICE,
            )
        )
    with pytest.raises(ValueError):
        decode_schedule_applied(
            _event(
                event_id=event_id,
                event_type=SCHEDULE_APPLIED,
                payload=dict(payload),
                actor=PrincipalKind.HUMAN,
            )
        )
    with pytest.raises(ValueError):
        decode_schedule_applied(
            _event(
                event_id=event_id,
                event_type=SCHEDULE_APPLIED,
                payload={**payload, "policy": {**payload["policy"], "provider": "fsrs"}},
                actor=PrincipalKind.SERVICE,
            )
        )  # type: ignore[index]
