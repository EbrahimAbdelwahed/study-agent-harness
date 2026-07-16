"""Authority-safe application service for canonical assessment commands."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from typing import TypeVar, cast

from study_agent.artifacts.content import AssessmentItemContent
from study_agent.domain import (
    Actor,
    ArtifactRevisionId,
    ArtifactRevisionStatus,
    AssessmentFormat,
    AttemptId,
    CourseId,
    DomainEvent,
    EventId,
    ExecutionContext,
    GradeId,
    GradeLifecycle,
    GradeStatus,
    PresentationId,
    PrincipalKind,
    SessionId,
    StudyArtifactKind,
    assessment_event_id_for,
    attempt_id_for,
    grade_id_for,
    presentation_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.ports import (
    ArtifactViewPort,
    AssessmentViewPort,
    ClockPort,
    EventSequenceConflictError,
    EventStore,
    SessionViewPort,
)
from study_agent.ports.assessment import DeterministicClosedGradingPolicyPort
from study_agent.state import canonical_json_bytes

from .contracts import (
    AttemptRecord,
    CanonicalResponse,
    DeterministicGradeProvenance,
    FreeResponse,
    GradeContestRecord,
    GradeRecord,
    MultipleChoiceResponse,
    PresentationRecord,
    SingleChoiceResponse,
)
from .events import (
    ASSESSMENT_SCHEMA_VERSION,
    ATTEMPT_RECORDED,
    GRADE_CONTESTED,
    GRADE_RECORDED,
    ITEM_PRESENTED,
    attempt_recorded_payload,
    decode_item_presented,
    grade_contested_payload,
    grade_recorded_payload,
    item_presented_payload,
)
from .grading import ExactClosedGradingPolicy

_RecordT = TypeVar("_RecordT", PresentationRecord, AttemptRecord, GradeRecord, GradeContestRecord)


class AssessmentCommandError(ValueError):
    """An assessment command violates authority, ownership, or ordering."""


class AssessmentConflictError(AssessmentCommandError):
    """A retry identity or immutable assessment target conflicts with state."""


class RetryableAssessmentConflictError(RuntimeError):
    """The caller must reload the course sequence and retry deliberately."""


class AssessmentService:
    def __init__(
        self,
        events: EventStore,
        clock: ClockPort,
        view: AssessmentViewPort,
        artifacts: ArtifactViewPort,
        sessions: SessionViewPort,
        grading_policy: DeterministicClosedGradingPolicyPort | None = None,
    ) -> None:
        self._events = events
        self._clock = clock
        self._view = view
        self._artifacts = artifacts
        self._sessions = sessions
        self._grading_policy = grading_policy or ExactClosedGradingPolicy()

    def present_item(
        self,
        revision_id: ArtifactRevisionId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> PresentationRecord:
        session_id, key = self._context(context, PrincipalKind.SERVICE)
        _expected_sequence(expected_sequence)
        if not isinstance(revision_id, ArtifactRevisionId):
            raise TypeError("revision_id must be ArtifactRevisionId")
        event_id = assessment_event_id_for(context.course_id, session_id, key, ITEM_PRESENTED)
        prior = self._event(event_id, context)
        if prior is not None:
            decoded = decode_item_presented(prior)
            if decoded.revision_id != revision_id:
                raise AssessmentConflictError("idempotency key names another presentation")
            return self._view.get(context.course_id).presentation(decoded.presentation_id)

        artifacts = self._artifacts.get(context.course_id)
        try:
            revision = artifacts.revision(revision_id)
        except LookupError as error:
            raise AssessmentCommandError("assessment artifact revision was not found") from error
        batch = next((item for item in artifacts.batches if item.id == revision.batch_id), None)
        if (
            revision.status is not ArtifactRevisionStatus.ACCEPTED
            or revision.kind is not StudyArtifactKind.ASSESSMENT_ITEM
            or batch is None
            or batch.session_id != session_id
            or not isinstance(revision.content.content, AssessmentItemContent)
        ):
            raise AssessmentCommandError(
                "presentation requires an accepted assessment item owned by this session"
            )
        content = revision.content.content
        encoded = revision.content.to_bytes()
        payload = item_presented_payload(
            revision_id,
            sha256(encoded).hexdigest(),
            content.format,
            content.prompt,
            content.options,
            key,
            course_id=context.course_id,
            session_id=session_id,
        )
        presentation_id = presentation_id_for(
            context.course_id, session_id, revision_id, key
        )
        event = self._domain_event(context, event_id, ITEM_PRESENTED, expected_sequence, payload)
        return self._append(
            context,
            expected_sequence,
            event,
            cast(str, payload["command_fingerprint"]),
            lambda: self._view.get(context.course_id).presentation(presentation_id),
        )

    def record_attempt(
        self,
        presentation_id: PresentationId,
        response: CanonicalResponse,
        latency_ms: int | None,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> AttemptRecord:
        session_id, key = self._context(context, PrincipalKind.HUMAN)
        _expected_sequence(expected_sequence)
        if not isinstance(presentation_id, PresentationId):
            raise TypeError("presentation_id must be PresentationId")
        if not isinstance(response, (FreeResponse, SingleChoiceResponse, MultipleChoiceResponse)):
            raise TypeError("response is not canonical")
        payload = attempt_recorded_payload(
            presentation_id,
            response,
            latency_ms,
            key,
            course_id=context.course_id,
            session_id=session_id,
        )
        attempt_id = attempt_id_for(context.course_id, session_id, presentation_id, key)
        event_id = assessment_event_id_for(context.course_id, session_id, key, ATTEMPT_RECORDED)
        existing = self._exact_retry(event_id, context, cast(str, payload["command_fingerprint"]))
        if existing:
            return self._view.get(context.course_id).attempt(attempt_id)
        snapshot = self._view.get(context.course_id)
        try:
            presentation = snapshot.presentation(presentation_id)
        except LookupError as error:
            raise AssessmentCommandError("attempt presentation was not found") from error
        if presentation.session_id != session_id:
            raise AssessmentCommandError("attempt presentation belongs to another session")
        if any(item.presentation_id == presentation_id for item in snapshot.attempts):
            raise AssessmentConflictError("presentation already has a learner attempt")
        event = self._domain_event(context, event_id, ATTEMPT_RECORDED, expected_sequence, payload)
        return self._append(
            context,
            expected_sequence,
            event,
            cast(str, payload["command_fingerprint"]),
            lambda: self._view.get(context.course_id).attempt(attempt_id),
        )

    def grade_closed(
        self,
        attempt_id: AttemptId,
        context: ExecutionContext,
        expected_sequence: int,
        *,
        supersedes_grade_id: GradeId | None = None,
    ) -> GradeRecord:
        session_id, key = self._context(context, PrincipalKind.SERVICE)
        _expected_sequence(expected_sequence)
        if not isinstance(attempt_id, AttemptId):
            raise TypeError("attempt_id must be AttemptId")
        if supersedes_grade_id is not None and not isinstance(supersedes_grade_id, GradeId):
            raise TypeError("supersedes_grade_id must be GradeId or absent")
        snapshot = self._view.get(context.course_id)
        try:
            attempt = snapshot.attempt(attempt_id)
            presentation = snapshot.presentation(attempt.presentation_id)
        except LookupError as error:
            raise AssessmentCommandError("closed grade target was not found") from error
        if attempt.session_id != session_id or presentation.session_id != session_id:
            raise AssessmentCommandError("closed grade target belongs to another session")
        if presentation.content.format is AssessmentFormat.FREE_RESPONSE:
            raise AssessmentCommandError("free responses require verified capability grading")
        decision = self._grading_policy.grade(presentation.content, attempt.response)
        rubric_fingerprint = sha256(
            canonical_json_bytes(
                {"evaluation_criteria": presentation.content.evaluation_criteria}
            )
        ).hexdigest()
        provenance = DeterministicGradeProvenance(
            decision.policy_id,
            decision.policy_version,
            decision.policy_fingerprint,
            rubric_fingerprint,
        )
        payload = grade_recorded_payload(
            attempt_id,
            GradeStatus.GRADED,
            decision.criterion_results,
            decision.score,
            provenance,
            supersedes_grade_id,
            key,
            course_id=context.course_id,
            session_id=session_id,
        )
        grade_id = grade_id_for(context.course_id, session_id, attempt_id, key)
        event_id = assessment_event_id_for(context.course_id, session_id, key, GRADE_RECORDED)
        existing = self._exact_retry(event_id, context, cast(str, payload["command_fingerprint"]))
        if existing:
            return self._view.get(context.course_id).grade(grade_id)
        active = tuple(
            item
            for item in snapshot.grades
            if item.attempt_id == attempt_id and item.lifecycle is GradeLifecycle.ACTIVE
        )
        if not active and supersedes_grade_id is not None:
            raise AssessmentConflictError("initial grade cannot name a predecessor")
        if active and (len(active) != 1 or active[0].id != supersedes_grade_id):
            raise AssessmentConflictError("successor grade must name the exact active predecessor")
        event = self._domain_event(context, event_id, GRADE_RECORDED, expected_sequence, payload)
        return self._append(
            context,
            expected_sequence,
            event,
            cast(str, payload["command_fingerprint"]),
            lambda: self._view.get(context.course_id).grade(grade_id),
        )

    def contest_grade(
        self,
        grade_id: GradeId,
        reason: str,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> GradeContestRecord:
        session_id, key = self._context(context, PrincipalKind.HUMAN)
        _expected_sequence(expected_sequence)
        if not isinstance(grade_id, GradeId):
            raise TypeError("grade_id must be GradeId")
        payload = grade_contested_payload(grade_id, reason, key)
        event_id = assessment_event_id_for(context.course_id, session_id, key, GRADE_CONTESTED)
        existing = self._exact_retry(event_id, context, cast(str, payload["command_fingerprint"]))
        snapshot = self._view.get(context.course_id)
        if existing:
            return _contest(snapshot.contests, grade_id)
        try:
            grade = snapshot.grade(grade_id)
        except LookupError as error:
            raise AssessmentCommandError("contested grade was not found") from error
        if grade.session_id != session_id:
            raise AssessmentCommandError("contested grade belongs to another session")
        if any(item.grade_id == grade_id for item in snapshot.contests):
            raise AssessmentConflictError("grade was already contested")
        event = self._domain_event(context, event_id, GRADE_CONTESTED, expected_sequence, payload)
        return self._append(
            context,
            expected_sequence,
            event,
            cast(str, payload["command_fingerprint"]),
            lambda: _contest(self._view.get(context.course_id).contests, grade_id),
        )

    def _context(
        self, context: ExecutionContext, authority: PrincipalKind
    ) -> tuple[SessionId, str]:
        if not isinstance(context, ExecutionContext):
            raise TypeError("context must be ExecutionContext")
        if context.principal_kind is not authority:
            raise AssessmentCommandError(
                f"assessment command requires {authority.value.upper()} authority"
            )
        if context.session_id is None or context.idempotency_key is None:
            raise AssessmentCommandError("assessment command requires session and retry identity")
        session = self._sessions.get_session(context.course_id, context.session_id)
        if session.course_id != context.course_id or session.id != context.session_id:
            raise AssessmentCommandError("execution context does not own the session")
        return context.session_id, context.idempotency_key

    def _event(self, event_id: EventId, context: ExecutionContext) -> DomainEvent | None:
        matches = tuple(
            item
            for item in self._events.read(context.course_id)
            if item.event_id == event_id
        )
        if len(matches) > 1:
            raise ValueError("course stream contains duplicate assessment event identities")
        return matches[0] if matches else None

    def _exact_retry(
        self, event_id: EventId, context: ExecutionContext, command_fingerprint: str
    ) -> bool:
        existing = self._event(event_id, context)
        if existing is None:
            return False
        if existing.payload.get("command_fingerprint") != command_fingerprint:
            raise AssessmentConflictError("idempotency key names a different command")
        return True

    def _domain_event(
        self,
        context: ExecutionContext,
        event_id: EventId,
        event_type: str,
        expected_sequence: int,
        payload: JsonObject,
    ) -> DomainEvent:
        return DomainEvent(
            event_id,
            context.course_id,
            expected_sequence + 1,
            event_type,
            ASSESSMENT_SCHEMA_VERSION,
            Actor(context.principal_kind, context.principal_id),
            self._clock.now(),
            context.correlation_id,
            payload,
            context.session_id,
        )

    def _append(
        self,
        context: ExecutionContext,
        expected_sequence: int,
        event: DomainEvent,
        command_fingerprint: str,
        result: Callable[[], _RecordT],
    ) -> _RecordT:
        actual = _current_sequence(self._events, context.course_id)
        if actual != expected_sequence:
            raise RetryableAssessmentConflictError(
                "course stream advanced before the assessment command"
            )
        try:
            self._events.append(context.course_id, expected_sequence, (event,))
        except EventSequenceConflictError as error:
            if self._exact_retry(event.event_id, context, command_fingerprint):
                return result()
            raise RetryableAssessmentConflictError(
                "course stream raced before the assessment command committed"
            ) from error
        return result()


def _contest(contests: tuple[GradeContestRecord, ...], grade_id: GradeId) -> GradeContestRecord:
    matches = tuple(item for item in contests if item.grade_id == grade_id)
    if len(matches) != 1:
        raise LookupError(f"one contest for grade {grade_id} was not found")
    return matches[0]


def _current_sequence(events: EventStore, course_id: CourseId) -> int:
    stream = events.read(course_id)
    return stream[-1].course_sequence if stream else 0


def _expected_sequence(value: int) -> None:
    if type(value) is not int:
        raise TypeError("expected_sequence must be an integer")
    if value < 0:
        raise ValueError("expected_sequence cannot be negative")


__all__ = [
    "AssessmentCommandError",
    "AssessmentConflictError",
    "AssessmentService",
    "RetryableAssessmentConflictError",
]
