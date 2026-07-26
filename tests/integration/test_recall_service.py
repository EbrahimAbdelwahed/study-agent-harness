from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from study_agent.domain import (
    ArtifactId,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    CorrelationId,
    CourseId,
    DomainEvent,
    ExecutionContext,
    PrincipalKind,
    SessionId,
    StudyArtifactKind,
    review_id_for,
)
from study_agent.domain._validation import JsonValue
from study_agent.ports.artifact import ArtifactViewPort
from study_agent.ports.storage import EventSequenceConflictError
from study_agent.recall import (
    RecallCommandError,
    RecallConflictError,
    RecallRating,
    RecallService,
    RetryableRecallConflictError,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    effective_policy_fingerprint,
    result_fingerprint,
)
from study_agent.recall.events import register_recall_events
from study_agent.state import EventRegistry, Projection, apply_event

COURSE = CourseId("course-1")
SESSION = SessionId("session-1")
SECOND_SESSION = SessionId("session-2")
REVISION = ArtifactRevisionId("revision-1")
ARTIFACT = ArtifactId("artifact-1")
START = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)


@dataclass
class FakeClock:
    current: datetime = START

    def now(self) -> datetime:
        return self.current


class FakeScheduler:
    def __init__(self) -> None:
        self.requests: list[SchedulingRequest] = []
        self.drift = False

    def decide(self, request: SchedulingRequest) -> SchedulingResult:
        self.requests.append(request)
        partial = SchedulingResult(
            request.enrollment_at + timedelta(days=1 if not request.history else 2),
            "fake",
            "1",
            effective_policy_fingerprint(request.policy, "fake", "1", "fake", "1"),
            "fake",
            "1",
            request.history_fingerprint,
            "0" * 64,
        )
        result = replace(partial, result_fingerprint=result_fingerprint(request, partial))
        if self.drift:
            return replace(result, result_fingerprint="f" * 64)
        return result


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self.projection = Projection(COURSE, 0, _base_state())
        self.registry = EventRegistry()
        register_recall_events(self.registry)
        self.calls: list[tuple[int, int]] = []
        self.race = False

    def append(self, course_id, expected_sequence, events):  # type: ignore[no-untyped-def]
        self.calls.append((expected_sequence, len(events)))
        if self.race:
            self.race = False
            raise EventSequenceConflictError(course_id, expected_sequence, expected_sequence + 1)
        if expected_sequence != self.projection.sequence:
            raise EventSequenceConflictError(course_id, expected_sequence, self.projection.sequence)
        next_projection = self.projection
        for event in events:
            next_projection = apply_event(next_projection, event, self.registry)
        self.projection = next_projection
        self.events.extend(events)
        return self.projection.sequence

    def read(self, course_id, after_sequence=0):  # type: ignore[no-untyped-def]
        return tuple(event for event in self.events if event.course_sequence > after_sequence)


class MutableRecallView:
    def __init__(self, store: MemoryEventStore) -> None:
        self.store = store

    def get(self, course_id):  # type: ignore[no-untyped-def]
        from study_agent.recall.view import ProjectionRecallView

        return ProjectionRecallView(lambda _: self.store.projection).get(course_id)


def _base_state() -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {
        "course": {"course_id": str(COURSE)},
        "sessions": {
            str(SESSION): {"course_id": str(COURSE)},
            str(SECOND_SESSION): {"course_id": str(COURSE)},
        },
        "study_artifacts": {
            "revisions": {
                str(REVISION): {
                    "status": ArtifactRevisionStatus.ACCEPTED.value,
                    "kind": StudyArtifactKind.FLASHCARD.value,
                }
            }
        },
        },
    )


def _artifact_view() -> ArtifactViewPort:
    target = SimpleNamespace(
        id=REVISION,
        artifact_id=ARTIFACT,
        batch_id="batch-1",
        status=ArtifactRevisionStatus.ACCEPTED,
        kind=StudyArtifactKind.FLASHCARD,
    )
    batch = SimpleNamespace(id="batch-1", session_id=SESSION)
    snapshot = SimpleNamespace(
        revision=lambda requested: (
            target if requested == REVISION else (_ for _ in ()).throw(LookupError())
        ),
        batches=(batch,),
    )
    return cast(ArtifactViewPort, SimpleNamespace(get=lambda course_id: snapshot))


def _context(
    kind: PrincipalKind, key: str, session_id: SessionId = SESSION
) -> ExecutionContext:
    return ExecutionContext(
        kind,
        kind.value,
        COURSE,
        CorrelationId("corr"),
        session_id=session_id,
        idempotency_key=key,
    )


def _service(
    clock: FakeClock | None = None,
    scheduler: FakeScheduler | None = None,
    store: MemoryEventStore | None = None,
) -> tuple[RecallService, FakeClock, FakeScheduler, MemoryEventStore]:
    actual_clock = clock or FakeClock()
    actual_scheduler = scheduler or FakeScheduler()
    actual_store = store or MemoryEventStore()
    return (
        RecallService(
            actual_store,
            actual_clock,
            _artifact_view(),
            actual_scheduler,
            MutableRecallView(actual_store),
        ),
        actual_clock,
        actual_scheduler,
        actual_store,
    )


def test_enroll_calls_scheduler_before_one_cas_and_is_exactly_retryable() -> None:
    service, clock, scheduler, store = _service()
    first = service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    assert len(scheduler.requests) == 1
    assert store.calls == [(0, 1)]
    assert first.enrollments[0].revision_id == REVISION
    retry = service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    assert retry == first
    assert len(scheduler.requests) == 1
    assert clock.current == START


def test_review_scheduler_runs_before_atomic_review_schedule_append() -> None:
    service, clock, scheduler, store = _service()
    service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    clock.current = START + timedelta(hours=1)
    reviewed = service.review(
        REVISION,
        RecallRating.GOOD,
        _context(PrincipalKind.HUMAN, "review"),
        1,
        latency_ms=400,
        confidence_bps=9000,
    )
    assert len(scheduler.requests) == 2
    assert store.calls[-1] == (1, 2)
    assert [event.actor.kind for event in store.events[-2:]] == [
        PrincipalKind.HUMAN,
        PrincipalKind.SERVICE,
    ]
    assert len(reviewed.reviews) == 1
    assert len(reviewed.schedules) == 2
    assert scheduler.requests[-1].history[0].review_id == reviewed.reviews[0].review_id


def test_longitudinal_review_can_use_a_later_session_for_same_accepted_revision() -> None:
    service, clock, _, store = _service()
    service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    clock.current = START + timedelta(hours=1)
    reviewed = service.review(
        REVISION,
        RecallRating.GOOD,
        _context(PrincipalKind.HUMAN, "review-later", SECOND_SESSION),
        1,
    )
    assert reviewed.reviews[0].review_id == review_id_for(
        COURSE, SECOND_SESSION, REVISION, "review-later"
    )
    assert store.events[-2].session_id == SECOND_SESSION


def test_authority_and_revision_validation_are_fail_closed() -> None:
    service, _, _, _ = _service()
    with pytest.raises(RecallCommandError):
        service.enroll(REVISION, _context(PrincipalKind.HUMAN, "bad"), 0)
    with pytest.raises(RecallCommandError):
        service.review(REVISION, RecallRating.GOOD, _context(PrincipalKind.MODEL, "bad"), 0)


def test_scheduler_fingerprint_drift_fails_before_append() -> None:
    scheduler = FakeScheduler()
    scheduler.drift = True
    service, _, _, store = _service(scheduler=scheduler)
    with pytest.raises(RecallCommandError):
        service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    assert store.events == []


def test_retry_policy_is_resolved_even_when_argument_is_omitted() -> None:
    custom = replace(SchedulingPolicyConfigV1(), target_retention_bps=8500)
    service, _, _, _ = _service()
    service.enroll(
        REVISION,
        _context(PrincipalKind.SERVICE, "enroll-custom"),
        0,
        policy=custom,
    )
    with pytest.raises(RecallConflictError, match="another policy"):
        service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll-custom"), 0)


def test_race_without_commit_is_typed_retryable_and_atomic_batch_never_partially_writes() -> None:
    store = MemoryEventStore()
    service, _, _, _ = _service(store=store)
    store.race = True
    with pytest.raises(RetryableRecallConflictError):
        service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    assert store.events == []
    service.enroll(REVISION, _context(PrincipalKind.SERVICE, "enroll"), 0)
    store.race = True
    with pytest.raises(RetryableRecallConflictError):
        service.review(
            REVISION,
            RecallRating.GOOD,
            _context(PrincipalKind.HUMAN, "review"),
            1,
        )
    assert len(store.events) == 1
