"""Application service for canonical progressive study-context mutations."""

from __future__ import annotations

from study_agent.domain import (
    Actor,
    CourseId,
    DomainEvent,
    EventId,
    ExecutionContext,
    InteractionId,
    InteractionKind,
    PrincipalKind,
    SessionId,
    StatementId,
    StatementStatus,
    StudyContextSnapshot,
    StudyStatementInput,
    StudyStatementKind,
    statement_id_for,
    study_context_event_id_for,
)
from study_agent.domain._validation import JsonObject
from study_agent.ports import (
    ClockPort,
    CourseViewPort,
    EventSequenceConflictError,
    EventStore,
    SessionViewPort,
)
from study_agent.ports.study_context import StudyContextViewPort

from .events import (
    CONFLICT_RESOLVED,
    STATEMENT_RECORDED,
    STATEMENT_RETRACTED,
    STUDY_CONTEXT_SCHEMA_VERSION,
    conflict_resolved_payload,
    record_command_fingerprint,
    resolve_command_fingerprint,
    retract_command_fingerprint,
    statement_recorded_payload,
    statement_retracted_payload,
)


class StudyContextCommandError(ValueError):
    """A study-context command violates authority, ownership, or lifecycle rules."""


class StudyContextConflictError(StudyContextCommandError):
    """A retry identity or requested lifecycle target conflicts with canonical state."""


class RetryableStudyContextConflictError(RuntimeError):
    """The caller must reload the course sequence before issuing a new command."""


class StudyContextService:
    def __init__(
        self,
        events: EventStore,
        clock: ClockPort,
        view: StudyContextViewPort,
        courses: CourseViewPort,
        sessions: SessionViewPort,
    ) -> None:
        self._events = events
        self._clock = clock
        self._view = view
        self._courses = courses
        self._sessions = sessions

    def record(
        self,
        statement: StudyStatementInput,
        origin_interaction_id: InteractionId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> StudyContextSnapshot:
        session_id, key = self._context(context)
        _validate_expected_sequence(expected_sequence)
        if not isinstance(statement, StudyStatementInput):
            raise TypeError("statement must be a StudyStatementInput")
        if not isinstance(origin_interaction_id, InteractionId):
            raise TypeError("origin_interaction_id must be an InteractionId")
        event_id = study_context_event_id_for(context.course_id, session_id, key, "record")
        fingerprint = record_command_fingerprint(statement, origin_interaction_id)
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        self._expect_sequence(context, expected_sequence)
        interactions = self._sessions.interactions(context.course_id, session_id)
        origin = next(
            (item for item in interactions if item.id == origin_interaction_id), None
        )
        if origin is None or origin.kind is not InteractionKind.HUMAN:
            raise StudyContextCommandError(
                "origin interaction must be an existing human interaction in the session"
            )
        statement_id = statement_id_for(event_id)
        event = self._event(
            context,
            event_id,
            STATEMENT_RECORDED,
            expected_sequence + 1,
            statement_recorded_payload(
                statement_id, origin_interaction_id, statement, session_id, key
            ),
        )
        return self._append(context, expected_sequence, event, fingerprint)

    def retract(
        self,
        statement_id: StatementId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> StudyContextSnapshot:
        session_id, key = self._context(context)
        _validate_expected_sequence(expected_sequence)
        if not isinstance(statement_id, StatementId):
            raise TypeError("statement_id must be a StatementId")
        event_id = study_context_event_id_for(context.course_id, session_id, key, "retract")
        fingerprint = retract_command_fingerprint(statement_id)
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        self._expect_sequence(context, expected_sequence)
        try:
            target = self._view.get(context.course_id).statement(statement_id)
        except LookupError as error:
            raise StudyContextCommandError("retraction target was not found") from error
        if target.status is not StatementStatus.ACTIVE:
            raise StudyContextConflictError("retraction target is not active")
        event = self._event(
            context,
            event_id,
            STATEMENT_RETRACTED,
            expected_sequence + 1,
            statement_retracted_payload(statement_id, session_id, key),
        )
        return self._append(context, expected_sequence, event, fingerprint)

    def resolve(
        self,
        kind: StudyStatementKind,
        selected_statement_id: StatementId,
        context: ExecutionContext,
        expected_sequence: int,
    ) -> StudyContextSnapshot:
        session_id, key = self._context(context)
        _validate_expected_sequence(expected_sequence)
        if not isinstance(kind, StudyStatementKind):
            raise TypeError("kind must be a StudyStatementKind")
        if not isinstance(selected_statement_id, StatementId):
            raise TypeError("selected_statement_id must be a StatementId")
        if not kind.is_scalar:
            raise StudyContextCommandError("only scalar statement kinds can be resolved")
        event_id = study_context_event_id_for(context.course_id, session_id, key, "resolve")
        fingerprint = resolve_command_fingerprint(kind, selected_statement_id)
        existing = self._existing(context, event_id, fingerprint)
        if existing is not None:
            return existing
        self._expect_sequence(context, expected_sequence)
        snapshot = self._view.get(context.course_id)
        conflict = next((item for item in snapshot.conflicts if item.kind is kind), None)
        if conflict is None:
            raise StudyContextConflictError("resolution requires a current scalar conflict")
        try:
            selected = snapshot.statement(selected_statement_id)
        except LookupError as error:
            raise StudyContextCommandError("resolution winner was not found") from error
        if selected.kind is not kind or selected.status is not StatementStatus.ACTIVE:
            raise StudyContextConflictError("resolution winner is not active for this kind")
        losers = tuple(
            sorted(
                (
                    item.id
                    for item in snapshot.active(kind)
                    if item.value != selected.value
                ),
                key=str,
            )
        )
        event = self._event(
            context,
            event_id,
            CONFLICT_RESOLVED,
            expected_sequence + 1,
            conflict_resolved_payload(
                kind, selected_statement_id, losers, session_id, key
            ),
        )
        return self._append(context, expected_sequence, event, fingerprint)

    def _context(self, context: ExecutionContext) -> tuple[SessionId, str]:
        if context.principal_kind not in (PrincipalKind.HUMAN, PrincipalKind.SERVICE):
            raise StudyContextCommandError(
                "study-context writes require human or service authority"
            )
        if context.session_id is None:
            raise StudyContextCommandError("study-context writes require a session")
        if context.idempotency_key is None:
            raise StudyContextCommandError("study-context writes require an idempotency key")
        self._courses.get(context.course_id)
        session = self._sessions.get_session(context.course_id, context.session_id)
        if session.course_id != context.course_id or session.id != context.session_id:
            raise StudyContextCommandError("execution context does not own the session")
        return context.session_id, context.idempotency_key

    def _existing(
        self, context: ExecutionContext, event_id: EventId, fingerprint: str
    ) -> StudyContextSnapshot | None:
        prior = self._view.command_fingerprint(context.course_id, event_id)
        if prior is None:
            return None
        if prior != fingerprint:
            raise StudyContextConflictError("idempotency key names a different command")
        return self._view.get(context.course_id)

    def _expect_sequence(self, context: ExecutionContext, expected_sequence: int) -> None:
        actual = _current_sequence(self._events, context.course_id)
        if expected_sequence != actual:
            raise RetryableStudyContextConflictError(
                "course stream advanced before the study-context command"
            )

    def _append(
        self,
        context: ExecutionContext,
        expected_sequence: int,
        event: DomainEvent,
        fingerprint: str,
    ) -> StudyContextSnapshot:
        try:
            self._events.append(context.course_id, expected_sequence, (event,))
        except EventSequenceConflictError as error:
            existing = self._existing(context, event.event_id, fingerprint)
            if existing is not None:
                return existing
            raise RetryableStudyContextConflictError(
                "course stream raced before the study-context command committed"
            ) from error
        return self._view.get(context.course_id)

    def _event(
        self,
        context: ExecutionContext,
        event_id: EventId,
        event_type: str,
        sequence: int,
        payload: JsonObject,
    ) -> DomainEvent:
        return DomainEvent(
            event_id=event_id,
            course_id=context.course_id,
            course_sequence=sequence,
            event_type=event_type,
            schema_version=STUDY_CONTEXT_SCHEMA_VERSION,
            actor=Actor(context.principal_kind, context.principal_id),
            occurred_at=self._clock.now(),
            correlation_id=context.correlation_id,
            payload=payload,
            session_id=context.session_id,
        )


def _current_sequence(events: EventStore, course_id: CourseId) -> int:
    stream = events.read(course_id)
    return stream[-1].course_sequence if stream else 0


def _validate_expected_sequence(expected_sequence: int) -> None:
    if not isinstance(expected_sequence, int) or isinstance(expected_sequence, bool):
        raise TypeError("expected_sequence must be an integer")
    if expected_sequence < 0:
        raise ValueError("expected_sequence cannot be negative")
