from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ._validation import require_text


@dataclass(frozen=True, slots=True)
class Identifier:
    """A validated, immutable identifier with type-sensitive equality."""

    value: str

    def __post_init__(self) -> None:
        require_text(self.value, type(self).__name__)

    def __str__(self) -> str:
        return self.value


class CourseId(Identifier):
    pass


class SourceId(Identifier):
    pass


class RevisionId(Identifier):
    pass


class ChunkId(Identifier):
    pass


class SessionId(Identifier):
    pass


class InteractionId(Identifier):
    pass


class StatementId(Identifier):
    pass


class AnswerId(Identifier):
    pass


class EventId(Identifier):
    pass


class RunId(Identifier):
    pass


class ModelRunId(Identifier):
    pass


class CorrelationId(Identifier):
    pass


class BlobId(Identifier):
    pass


class ArtifactId(Identifier):
    pass


class ArtifactRevisionId(Identifier):
    pass


class ArtifactBatchId(Identifier):
    pass


class PresentationId(Identifier):
    pass


class AttemptId(Identifier):
    pass


class GradeId(Identifier):
    pass


class ReviewId(Identifier):
    """Stable identity of one learner review of one artifact revision."""

    pass


class ScheduleDecisionId(Identifier):
    """Stable identity of one applied scheduling decision."""

    pass


def artifact_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    retry_identity: str,
    command_kind: str,
) -> EventId:
    require_text(retry_identity, "retry_identity")
    require_text(command_kind, "command_kind")
    payload = (
        f"artifact-event@1\0{course_id}\0{session_id}\0{retry_identity}\0{command_kind}"
    ).encode()
    return EventId(f"event-sha256:{sha256(payload).hexdigest()}")


def presentation_id_for(
    course_id: CourseId,
    session_id: SessionId,
    revision_id: ArtifactRevisionId,
    retry_identity: str,
) -> PresentationId:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("presentation identity requires typed course and session ids")
    if not isinstance(revision_id, ArtifactRevisionId):
        raise TypeError("presentation identity requires ArtifactRevisionId")
    return PresentationId(
        "presentation-sha256:"
        f"{_assessment_digest(course_id, session_id, revision_id, retry_identity, 'presentation')}"
    )


def attempt_id_for(
    course_id: CourseId,
    session_id: SessionId,
    presentation_id: PresentationId,
    retry_identity: str,
) -> AttemptId:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("attempt identity requires typed course and session ids")
    if not isinstance(presentation_id, PresentationId):
        raise TypeError("attempt identity requires PresentationId")
    return AttemptId(
        "attempt-sha256:"
        f"{_assessment_digest(course_id, session_id, presentation_id, retry_identity, 'attempt')}"
    )


def grade_id_for(
    course_id: CourseId,
    session_id: SessionId,
    attempt_id: AttemptId,
    retry_identity: str,
) -> GradeId:
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("grade identity requires typed course and session ids")
    if not isinstance(attempt_id, AttemptId):
        raise TypeError("grade identity requires AttemptId")
    return GradeId(
        "grade-sha256:"
        f"{_assessment_digest(course_id, session_id, attempt_id, retry_identity, 'grade')}"
    )


def review_id_for(
    course_id: CourseId,
    session_id: SessionId,
    revision_id: ArtifactRevisionId,
    retry_identity: str,
) -> ReviewId:
    """Derive review identity from trusted scope and retry inputs only."""
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("review identity requires typed course and session ids")
    if not isinstance(revision_id, ArtifactRevisionId):
        raise TypeError("review identity requires ArtifactRevisionId")
    require_text(retry_identity, "retry_identity")
    raw = f"recall-review@1\0{course_id}\0{session_id}\0{revision_id}\0{retry_identity}".encode()
    return ReviewId(f"review-sha256:{sha256(raw).hexdigest()}")


def schedule_decision_id_for(
    course_id: CourseId,
    session_id: SessionId,
    revision_id: ArtifactRevisionId,
    trigger: str,
    identity: str,
) -> ScheduleDecisionId:
    """Derive an enrollment/review decision identity without scheduler output."""
    if not isinstance(course_id, CourseId) or not isinstance(session_id, SessionId):
        raise TypeError("schedule identity requires typed course and session ids")
    if not isinstance(revision_id, ArtifactRevisionId):
        raise TypeError("schedule identity requires ArtifactRevisionId")
    require_text(trigger, "trigger")
    require_text(identity, "identity")
    raw = (
        f"recall-schedule@1\0{course_id}\0{session_id}\0"
        f"{revision_id}\0{trigger}\0{identity}"
    ).encode()
    return ScheduleDecisionId(f"schedule-sha256:{sha256(raw).hexdigest()}")


def enrollment_decision_id_for(
    course_id: CourseId,
    session_id: SessionId,
    revision_id: ArtifactRevisionId,
    retry_identity: str,
) -> ScheduleDecisionId:
    return schedule_decision_id_for(
        course_id, session_id, revision_id, "enrollment", retry_identity
    )


def review_decision_id_for(
    course_id: CourseId,
    session_id: SessionId,
    revision_id: ArtifactRevisionId,
    review_id: ReviewId,
) -> ScheduleDecisionId:
    if not isinstance(review_id, ReviewId):
        raise TypeError("review decision identity requires ReviewId")
    return schedule_decision_id_for(
        course_id, session_id, revision_id, "review", str(review_id)
    )


def recall_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    retry_identity: str,
    event_type: str,
) -> EventId:
    require_text(retry_identity, "retry_identity")
    require_text(event_type, "event_type")
    raw = f"recall-event@1\0{course_id}\0{session_id}\0{retry_identity}\0{event_type}".encode()
    return EventId(f"event-sha256:{sha256(raw).hexdigest()}")


def assessment_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    retry_identity: str,
    event_type: str,
) -> EventId:
    require_text(retry_identity, "retry_identity")
    require_text(event_type, "event_type")
    payload = (
        f"assessment-event@1\0{course_id}\0{session_id}\0{retry_identity}\0{event_type}"
    ).encode()
    return EventId(f"event-sha256:{sha256(payload).hexdigest()}")


def _assessment_digest(
    course_id: CourseId,
    session_id: SessionId,
    target_id: Identifier,
    retry_identity: str,
    purpose: str,
) -> str:
    require_text(retry_identity, "retry_identity")
    payload = (
        f"assessment-identity@1\0{course_id}\0{session_id}\0{target_id}\0"
        f"{retry_identity}\0{purpose}"
    ).encode()
    return sha256(payload).hexdigest()


def answer_id_for(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    idempotency_key: str,
) -> AnswerId:
    return AnswerId(
        f"answer-sha256:{_retry_digest(course_id, session_id, run_id, idempotency_key, 'answer')}"
    )


def question_interaction_id_for(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    idempotency_key: str,
) -> InteractionId:
    return InteractionId(
        "interaction-sha256:"
        f"{_retry_digest(course_id, session_id, run_id, idempotency_key, 'question')}"
    )


def assistant_interaction_id_for(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    idempotency_key: str,
) -> InteractionId:
    return InteractionId(
        "interaction-sha256:"
        f"{_retry_digest(course_id, session_id, run_id, idempotency_key, 'assistant')}"
    )


def learner_interaction_id_for(
    course_id: CourseId,
    session_id: SessionId,
    idempotency_key: str,
) -> InteractionId:
    require_text(idempotency_key, "idempotency_key")
    identity = f"session-learner-turn@1\0{course_id}\0{session_id}\0{idempotency_key}".encode()
    return InteractionId(f"interaction-sha256:{sha256(identity).hexdigest()}")


def session_turn_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    idempotency_key: str,
    event_type: str,
) -> EventId:
    require_text(idempotency_key, "idempotency_key")
    require_text(event_type, "event_type")
    identity = (
        f"session-turn-event@1\0{course_id}\0{session_id}\0"
        f"{idempotency_key}\0{event_type}"
    ).encode()
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")


def session_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    idempotency_key: str,
    event_type: str,
) -> EventId:
    require_text(event_type, "event_type")
    return EventId(
        "event-sha256:"
        f"{_retry_digest(course_id, session_id, run_id, idempotency_key, event_type)}"
    )


def study_context_event_id_for(
    course_id: CourseId,
    session_id: SessionId,
    idempotency_key: str,
    command_kind: str,
) -> EventId:
    """Return the stable identity of one study-context command."""
    require_text(idempotency_key, "idempotency_key")
    require_text(command_kind, "command_kind")
    identity = (
        f"study-context@1\0{course_id}\0{session_id}\0{idempotency_key}\0{command_kind}"
    ).encode()
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")


def statement_id_for(command_event_id: EventId) -> StatementId:
    """Derive a statement identity from its canonical record command."""
    identity = f"study-context-statement@1\0{command_event_id}".encode()
    return StatementId(f"statement-sha256:{sha256(identity).hexdigest()}")


def _retry_digest(
    course_id: CourseId,
    session_id: SessionId,
    run_id: RunId,
    idempotency_key: str,
    purpose: str,
) -> str:
    require_text(idempotency_key, "idempotency_key")
    require_text(purpose, "purpose")
    identity = f"{course_id}\0{session_id}\0{run_id}\0{idempotency_key}\0{purpose}".encode()
    return sha256(identity).hexdigest()
