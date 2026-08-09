from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    CorrelationId,
    CourseId,
    DomainEvent,
    EventId,
    PrincipalKind,
    SessionId,
    enrollment_decision_id_for,
    recall_event_id_for,
    review_decision_id_for,
    review_id_for,
)
from study_agent.domain._validation import JsonValue
from study_agent.recall.contracts import (
    AppliedSchedule,
    RecallRating,
    ReviewRecord,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)
from study_agent.recall.events import (
    REVIEW_RECORDED,
    SCHEDULE_APPLIED,
    encode_review_recorded,
    encode_schedule_applied,
    register_recall_events,
)
from study_agent.state import EventRegistry, Projection, apply_event

COURSE = CourseId("course-1")
SESSION = SessionId("session-1")
REVISION = ArtifactRevisionId("revision-1")
NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
POLICY = SchedulingPolicyConfigV1()
FP = "a" * 64


def _state(kind: str = "flashcard", status: str = "accepted") -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {
        "course": {"course_id": str(COURSE)},
        "sessions": {str(SESSION): {"course_id": str(COURSE)}},
        "study_artifacts": {"revisions": {str(REVISION): {"status": status, "kind": kind}}},
        },
    )


def _mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    assert isinstance(value, Mapping)
    return value


def _event(
    event_type: str,
    event_id: EventId,
    sequence: int,
    actor: PrincipalKind,
    payload: Mapping[str, JsonValue],
    occurred_at: datetime = NOW,
) -> DomainEvent:
    return DomainEvent(
        event_id,
        COURSE,
        sequence,
        event_type,
        1,
        Actor(actor, "test"),
        occurred_at,
        CorrelationId("correlation-1"),
        payload,
        SESSION,
    )


def _result(request: SchedulingRequest, due_at: datetime) -> SchedulingResult:
    partial = SchedulingResult(
        due_at,
        "deterministic",
        "1",
        effective_policy_fingerprint(request.policy, "deterministic", "1", "fake", "1"),
        "fake",
        "1",
        request.history_fingerprint,
        "0" * 64,
    )
    return replace(partial, result_fingerprint=result_fingerprint(request, partial))


def _enrollment_event(sequence: int = 1) -> DomainEvent:
    key = "enroll-key"
    request = SchedulingRequest(REVISION, NOW, (), POLICY)
    result = _result(request, NOW + timedelta(days=1))
    schedule = AppliedSchedule(
        enrollment_decision_id_for(COURSE, SESSION, REVISION, key),
        REVISION,
        "enrollment",
        None,
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
        key,
        FP,
    )
    return _event(
        SCHEDULE_APPLIED,
        recall_event_id_for(COURSE, SESSION, key, SCHEDULE_APPLIED),
        sequence,
        PrincipalKind.SERVICE,
        encode_schedule_applied(schedule, course_id=COURSE, session_id=SESSION),
    )


def _review_event(sequence: int = 2) -> tuple[DomainEvent, ReviewRecord]:
    key = "review-key"
    review = ReviewRecord(
        review_id_for(COURSE, SESSION, REVISION, key),
        REVISION,
        RecallRating.GOOD,
        500,
        9000,
        NOW + timedelta(minutes=1),
        key,
        FP,
    )
    return (
        _event(
            REVIEW_RECORDED,
            recall_event_id_for(COURSE, SESSION, key, REVIEW_RECORDED),
            sequence,
            PrincipalKind.HUMAN,
            encode_review_recorded(review, course_id=COURSE, session_id=SESSION),
            occurred_at=review.occurred_at,
        ),
        review,
    )


def _review_schedule_event(review: ReviewRecord, sequence: int = 3) -> DomainEvent:
    request = SchedulingRequest(REVISION, NOW, (review.history_entry(),), POLICY)
    result = _result(request, NOW + timedelta(days=2))
    schedule = AppliedSchedule(
        review_decision_id_for(COURSE, SESSION, REVISION, review.review_id),
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
        "review-schedule-key",
        FP,
    )
    return _event(
        SCHEDULE_APPLIED,
        recall_event_id_for(COURSE, SESSION, schedule.idempotency_key, SCHEDULE_APPLIED),
        sequence,
        PrincipalKind.SERVICE,
        encode_schedule_applied(schedule, course_id=COURSE, session_id=SESSION),
    )


def _registry() -> EventRegistry:
    registry = EventRegistry()
    register_recall_events(registry)
    return registry


def test_replay_preserves_enrollment_review_and_matching_schedule() -> None:
    enrollment = _enrollment_event()
    review_event, review = _review_event()
    schedule = _review_schedule_event(review)
    registry = _registry()
    projection = Projection(COURSE, 0, _state())
    for event in (enrollment, review_event, schedule):
        projection = apply_event(projection, event, registry)
    recall = _mapping(projection.state["recall"])
    assert set(_mapping(recall["enrollments"])) == {str(REVISION)}
    assert set(_mapping(recall["reviews"])) == {str(review.review_id)}
    assert len(_mapping(recall["schedules"])) == 2
    replayed = Projection(COURSE, 0, _state())
    for event in (enrollment, review_event, schedule):
        replayed = apply_event(replayed, event, _registry())
    assert replayed.canonical_bytes() == projection.canonical_bytes()


def test_ordering_and_authority_fail_closed() -> None:
    enrollment = _enrollment_event()
    review_event, review = _review_event()
    schedule = _review_schedule_event(review)
    state = Projection(COURSE, 0, _state())
    registry = _registry()
    with pytest.raises(ValueError):
        apply_event(state, review_event, registry)
    after_enrollment = apply_event(state, enrollment, registry)
    with pytest.raises(ValueError):
        apply_event(after_enrollment, _review_schedule_event(review, 2), registry)
    with pytest.raises(ValueError):
        apply_event(
            after_enrollment,
            replace(review_event, actor=Actor(PrincipalKind.MODEL, "model")),
            registry,
        )
    assert (
        apply_event(
            apply_event(after_enrollment, review_event, registry), schedule, registry
        ).sequence
        == 3
    )


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("assessment_item", "accepted"),
        ("flashcard", "proposed"),
        ("flashcard", "rejected"),
        ("flashcard", "superseded"),
    ],
)
def test_only_current_accepted_flashcards_can_enroll_or_review(kind: str, status: str) -> None:
    with pytest.raises(ValueError):
        apply_event(Projection(COURSE, 0, _state(kind, status)), _enrollment_event(), _registry())


def test_reducer_rejects_forged_history_and_result_fingerprints() -> None:
    enrollment = _enrollment_event()
    review_event, review = _review_event()
    schedule = _review_schedule_event(review)
    state = Projection(COURSE, 0, _state())
    registry = _registry()
    after_review = apply_event(apply_event(state, enrollment, registry), review_event, registry)
    forged_payload = {**schedule.payload, "history_fingerprint": "f" * 64}
    forged = replace(schedule, payload=forged_payload)
    with pytest.raises(ValueError):
        apply_event(after_review, forged, registry)


def test_reducer_recomputes_review_identity_from_trusted_scope() -> None:
    enrollment = _enrollment_event()
    review_event, _review = _review_event()
    forged = replace(
        review_event,
        payload={
            **review_event.payload,
            "review_id": str(review_id_for(COURSE, SESSION, REVISION, "other-key")),
        },
    )
    registry = _registry()
    after_enrollment = apply_event(Projection(COURSE, 0, _state()), enrollment, registry)
    with pytest.raises(ValueError, match="trusted scope"):
        apply_event(after_enrollment, forged, registry)
