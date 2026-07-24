"""Authority-safe recall commands over the canonical course event stream."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    CourseId,
    DomainEvent,
    EventId,
    ExecutionContext,
    PrincipalKind,
    ReviewId,
    ScheduleDecisionId,
    SessionId,
    StudyArtifactKind,
    enrollment_decision_id_for,
    recall_event_id_for,
    review_decision_id_for,
    review_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.ports.artifact import ArtifactViewPort
from study_agent.ports.clock import ClockPort
from study_agent.ports.scheduling import SchedulingPolicyPort
from study_agent.ports.storage import EventSequenceConflictError, EventStore
from study_agent.state import canonical_json_bytes

from .contracts import (
    AppliedSchedule,
    RecallRating,
    RecallSnapshot,
    ReviewRecord,
    SchedulingPolicyConfigV1,
    SchedulingRequest,
    SchedulingResult,
    result_fingerprint,
)
from .events import (
    RECALL_SCHEMA_VERSION,
    REVIEW_RECORDED,
    SCHEDULE_APPLIED,
    decode_review_recorded,
    decode_schedule_applied,
    encode_review_recorded,
    encode_schedule_applied,
)

if TYPE_CHECKING:
    from study_agent.ports.recall import RecallViewPort


class RecallCommandError(ValueError):
    """A recall command violates authority, ownership, or validation rules."""


class RecallConflictError(RecallCommandError):
    """A retry identity or immutable recall target conflicts with state."""


class RetryableRecallConflictError(RuntimeError):
    """The course stream raced and the exact recall command did not commit."""


class RecallService:
    """Own HUMAN review evidence and SERVICE scheduling writes.

    The scheduler is always invoked before an append.  A review and its matching
    schedule are passed to the event store as one CAS batch, so replay can never
    observe an orphan review.
    """

    def __init__(
        self,
        events: EventStore,
        clock: ClockPort,
        artifacts: ArtifactViewPort,
        scheduler: SchedulingPolicyPort,
        recall_view: RecallViewPort,
        *,
        default_policy: SchedulingPolicyConfigV1 | None = None,
        service_principal_id: str = "recall-service",
    ) -> None:
        self._events = events
        self._clock = clock
        self._artifacts = artifacts
        self._scheduler = scheduler
        self._recall_view = recall_view
        self._default_policy = default_policy or SchedulingPolicyConfigV1()
        self._service_principal_id = service_principal_id

    def enroll(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        policy: SchedulingPolicyConfigV1 | None = None,
    ) -> RecallSnapshot:
        session_id, key = self._context(context, PrincipalKind.SERVICE)
        _expected_sequence(expected_sequence)
        if not isinstance(revision_id, ArtifactRevisionId):
            raise TypeError("revision_id must be ArtifactRevisionId")
        event_id = recall_event_id_for(context.course_id, session_id, key, SCHEDULE_APPLIED)
        existing = self._find_event(context.course_id, event_id)
        if existing is not None:
            decoded = decode_schedule_applied(existing)
            if (
                decoded.schedule.trigger != "enrollment"
                or decoded.schedule.revision_id != revision_id
            ):
                raise RecallConflictError("enrollment retry identity names another revision")
            effective_policy = policy if policy is not None else self._default_policy
            if decoded.schedule.policy != effective_policy:
                raise RecallConflictError("enrollment retry identity names another policy")
            return self._snapshot(context.course_id)

        self._accepted_target(context.course_id, revision_id)
        enrollment_at = _utc_now(self._clock.now())
        selected_policy = policy if policy is not None else self._default_policy
        request = SchedulingRequest(revision_id, enrollment_at, (), selected_policy)
        result = self._decide(request)
        schedule = self._schedule(
            context.course_id,
            session_id,
            context,
            enrollment_decision_id_for(context.course_id, session_id, revision_id, key),
            revision_id,
            "enrollment",
            None,
            request,
            result,
            key,
        )
        payload = encode_schedule_applied(
            schedule, course_id=context.course_id, session_id=session_id
        )
        event = self._event(
            context,
            event_id,
            SCHEDULE_APPLIED,
            expected_sequence + 1,
            payload,
            PrincipalKind.SERVICE,
            occurred_at=enrollment_at,
        )
        self._append_one(context.course_id, expected_sequence, event, schedule.command_fingerprint)
        return self._snapshot(context.course_id)

    def review(
        self,
        revision_id: ArtifactRevisionId,
        rating: RecallRating,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        latency_ms: int | None = None,
        confidence_bps: int | None = None,
        policy: SchedulingPolicyConfigV1 | None = None,
    ) -> RecallSnapshot:
        session_id, key = self._context(context, PrincipalKind.HUMAN)
        _expected_sequence(expected_sequence)
        if not isinstance(revision_id, ArtifactRevisionId):
            raise TypeError("revision_id must be ArtifactRevisionId")
        if not isinstance(rating, RecallRating):
            raise TypeError("rating must be RecallRating")
        _nonnegative(latency_ms, "latency_ms")
        _bounded_confidence(confidence_bps)
        review_event_id = recall_event_id_for(context.course_id, session_id, key, REVIEW_RECORDED)
        schedule_event_id = recall_event_id_for(
            context.course_id, session_id, key, SCHEDULE_APPLIED
        )
        existing_review = self._find_event(context.course_id, review_event_id)
        existing_schedule = self._find_event(context.course_id, schedule_event_id)
        if existing_review is not None or existing_schedule is not None:
            if existing_review is None or existing_schedule is None:
                if existing_schedule is not None:
                    try:
                        prior_schedule = decode_schedule_applied(existing_schedule).schedule
                    except ValueError as error:
                        raise RecallConflictError("review retry identity is malformed") from error
                    if prior_schedule.trigger != "review":
                        raise RecallConflictError("review retry identity names an enrollment")
                raise RetryableRecallConflictError("review and schedule did not commit atomically")
            decoded_review = decode_review_recorded(existing_review)
            decoded_schedule = decode_schedule_applied(existing_schedule)
            if (
                decoded_review.review.revision_id != revision_id
                or decoded_review.review.rating is not rating
                or decoded_review.review.latency_ms != latency_ms
                or decoded_review.review.confidence_bps != confidence_bps
                or decoded_schedule.schedule.review_id != decoded_review.review.review_id
            ):
                raise RecallConflictError("review retry identity names different evidence")
            effective_policy = (
                policy
                if policy is not None
                else self._review_policy(context.course_id, revision_id)
            )
            if decoded_schedule.schedule.policy != effective_policy:
                raise RecallConflictError("review retry identity names another policy")
            return self._snapshot(context.course_id)

        self._accepted_target(context.course_id, revision_id)
        before = self._snapshot(context.course_id)
        enrollment = next(
            (item for item in before.enrollments if item.revision_id == revision_id), None
        )
        if enrollment is None:
            raise RecallCommandError("review requires an enrolled accepted flashcard revision")
        occurred_at = _utc_now(self._clock.now())
        if occurred_at < enrollment.enrollment_at:
            raise RecallCommandError("review time precedes enrollment")
        prior_reviews = tuple(item for item in before.reviews if item.revision_id == revision_id)
        if prior_reviews and occurred_at <= max(item.occurred_at for item in prior_reviews):
            raise RecallCommandError("review time must advance monotonically")
        selected_policy = policy if policy is not None else enrollment.policy
        review = ReviewRecord(
            review_id_for(context.course_id, session_id, revision_id, key),
            revision_id,
            rating,
            latency_ms,
            confidence_bps,
            occurred_at,
            key,
            _review_command_fingerprint(
                revision_id, rating, latency_ms, confidence_bps, selected_policy
            ),
        )
        history = tuple(item.history_entry() for item in (*prior_reviews, review))
        request = SchedulingRequest(revision_id, enrollment.enrollment_at, history, selected_policy)
        result = self._decide(request)
        schedule = self._schedule(
            context.course_id,
            session_id,
            context,
            review_decision_id_for(context.course_id, session_id, revision_id, review.review_id),
            revision_id,
            "review",
            review.review_id,
            request,
            result,
            key,
        )
        review_payload = encode_review_recorded(
            review, course_id=context.course_id, session_id=session_id
        )
        schedule_payload = encode_schedule_applied(
            schedule, course_id=context.course_id, session_id=session_id
        )
        review_event = self._event(
            context,
            review_event_id,
            REVIEW_RECORDED,
            expected_sequence + 1,
            review_payload,
            PrincipalKind.HUMAN,
            occurred_at=occurred_at,
        )
        schedule_event = self._event(
            context,
            schedule_event_id,
            SCHEDULE_APPLIED,
            expected_sequence + 2,
            schedule_payload,
            PrincipalKind.SERVICE,
            occurred_at=occurred_at,
        )
        self._append_two(
            context.course_id,
            expected_sequence,
            (review_event, schedule_event),
            review.command_fingerprint,
            schedule.command_fingerprint,
        )
        return self._snapshot(context.course_id)

    def _accepted_target(
        self, course_id: CourseId, revision_id: ArtifactRevisionId
    ) -> None:
        try:
            snapshot = self._artifacts.get(course_id)
            target = snapshot.revision(revision_id)
        except (LookupError, ValueError) as error:
            raise RecallCommandError("recall target revision was not found") from error
        if (
            target.status is not ArtifactRevisionStatus.ACCEPTED
            or target.kind is not StudyArtifactKind.FLASHCARD
        ):
            raise RecallCommandError("recall target must be an accepted flashcard revision")
        return None

    def _review_policy(
        self, course_id: CourseId, revision_id: ArtifactRevisionId
    ) -> SchedulingPolicyConfigV1:
        snapshot = self._snapshot(course_id)
        enrollment = next(
            (item for item in snapshot.enrollments if item.revision_id == revision_id), None
        )
        if enrollment is None:
            raise RecallConflictError("review retry identity has no enrollment policy")
        return enrollment.policy

    def _decide(self, request: SchedulingRequest) -> SchedulingResult:
        try:
            result = self._scheduler.decide(request)
        except Exception as error:
            raise RecallCommandError("scheduling policy failed before append") from error
        if not isinstance(result, SchedulingResult):
            raise RecallCommandError("scheduler returned an invalid result")
        if result.due_at < request.enrollment_at:
            raise RecallCommandError("scheduler due_at precedes enrollment")
        if request.history and result.due_at < request.history[-1].occurred_at:
            raise RecallCommandError("scheduler due_at regresses review time")
        try:
            expected = result_fingerprint(request, result)
        except (TypeError, ValueError) as error:
            raise RecallCommandError("scheduler result fingerprint is invalid") from error
        if result.result_fingerprint != expected:
            raise RecallCommandError("scheduler result fingerprint is invalid")
        return result

    def _schedule(
        self,
        course_id: CourseId,
        session_id: SessionId,
        context: ExecutionContext,
        decision_id: ScheduleDecisionId,
        revision_id: ArtifactRevisionId,
        trigger: str,
        review_id: ReviewId | None,
        request: SchedulingRequest,
        result: SchedulingResult,
        key: str,
    ) -> AppliedSchedule:
        command_fingerprint = _schedule_command_fingerprint(request, result, trigger, review_id)
        return AppliedSchedule(
            decision_id,
            revision_id,
            trigger,
            review_id,
            request.enrollment_at,
            result.due_at,
            request.policy,
            result.policy_id,
            result.policy_version,
            result.policy_fingerprint,
            result.implementation_id,
            result.implementation_version,
            result.history_fingerprint,
            result.result_fingerprint,
            key,
            command_fingerprint,
        )

    def _context(
        self, context: ExecutionContext, authority: PrincipalKind
    ) -> tuple[SessionId, str]:
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be ExecutionContext")
        if context.principal_kind is not authority:
            raise RecallCommandError(f"recall command requires {authority.value.upper()} authority")
        if context.session_id is None or context.idempotency_key is None:
            raise RecallCommandError("recall command requires session and retry identity")
        return context.session_id, context.idempotency_key

    def _snapshot(self, course_id: CourseId) -> RecallSnapshot:
        return self._recall_view.get(course_id)

    def _find_event(self, course_id: CourseId, event_id: EventId) -> DomainEvent | None:
        matches = tuple(item for item in self._events.read(course_id) if item.event_id == event_id)
        if len(matches) > 1:
            raise RecallConflictError("course stream contains duplicate recall event identity")
        return matches[0] if matches else None

    def _event(
        self,
        context: ExecutionContext,
        event_id: EventId,
        event_type: str,
        sequence: int,
        payload: JsonObject,
        authority: PrincipalKind,
        *,
        occurred_at: datetime | None = None,
    ) -> DomainEvent:
        return DomainEvent(
            event_id,
            context.course_id,
            sequence,
            event_type,
            RECALL_SCHEMA_VERSION,
            Actor(
                authority,
                context.principal_id
                if authority is not PrincipalKind.SERVICE
                else self._service_principal_id,
            ),
            occurred_at or _utc_now(self._clock.now()),
            context.correlation_id,
            payload,
            context.session_id,
        )

    def _append_one(
        self, course_id: CourseId, expected: int, event: DomainEvent, fingerprint: str
    ) -> None:
        try:
            self._events.append(course_id, expected, (event,))
        except EventSequenceConflictError as error:
            existing = self._find_event(course_id, event.event_id)
            if existing is not None:
                if existing.payload.get("command_fingerprint") == fingerprint:
                    return
                raise RecallConflictError(
                    "recall retry identity committed different content"
                ) from error
            raise RetryableRecallConflictError(
                "course stream raced before recall command committed"
            ) from error

    def _append_two(
        self,
        course_id: CourseId,
        expected: int,
        events: tuple[DomainEvent, DomainEvent],
        review_fingerprint: str,
        schedule_fingerprint: str,
    ) -> None:
        try:
            self._events.append(course_id, expected, events)
        except EventSequenceConflictError as error:
            review_existing = self._find_event(course_id, events[0].event_id)
            schedule_existing = self._find_event(course_id, events[1].event_id)
            if review_existing is not None or schedule_existing is not None:
                if review_existing is not None and schedule_existing is not None:
                    if (
                        review_existing.payload.get("command_fingerprint") == review_fingerprint
                        and schedule_existing.payload.get("command_fingerprint")
                        == schedule_fingerprint
                    ):
                        return
                    raise RecallConflictError(
                        "recall retry identity committed different content"
                    ) from error
                raise RetryableRecallConflictError(
                    "review and schedule did not commit atomically"
                ) from error
            raise RetryableRecallConflictError(
                "course stream raced before recall command committed"
            ) from error


def _review_command_fingerprint(
    revision_id: ArtifactRevisionId,
    rating: RecallRating,
    latency_ms: int | None,
    confidence_bps: int | None,
    policy: SchedulingPolicyConfigV1,
) -> str:
    return _fingerprint(
        {
            "schema_version": 1,
            "revision_id": str(revision_id),
            "rating": rating.value,
            "latency_ms": latency_ms,
            "confidence_bps": confidence_bps,
            "policy_fingerprint": policy.fingerprint,
        }
    )


def _schedule_command_fingerprint(
    request: SchedulingRequest,
    result: SchedulingResult,
    trigger: str,
    review_id: object,
) -> str:
    return _fingerprint(
        {
            "schema_version": 1,
            "trigger": trigger,
            "review_id": str(review_id) if review_id is not None else None,
            "history_fingerprint": request.history_fingerprint,
            "result_fingerprint": result.result_fingerprint,
        }
    )


def _fingerprint(value: JsonObject) -> str:
    return sha256(b"recall-command@1\0" + canonical_json_bytes(value)).hexdigest()


def _utc_now(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RecallCommandError("clock must return an aware datetime")
    return value.astimezone(UTC)


def _nonnegative(value: int | None, name: str) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise RecallCommandError(f"{name} must be a non-negative integer or absent")


def _bounded_confidence(value: int | None) -> None:
    _nonnegative(value, "confidence_bps")
    if value is not None and value > 10000:
        raise RecallCommandError("confidence_bps must be in 0..10000")


def _expected_sequence(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("expected_sequence must be a non-negative integer")


__all__ = [
    "RecallCommandError",
    "RecallConflictError",
    "RecallService",
    "RetryableRecallConflictError",
]
