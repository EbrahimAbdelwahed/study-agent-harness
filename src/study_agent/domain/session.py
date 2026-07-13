from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ._validation import require_aware, require_text
from .grounding import AnswerStatus, GroundedAnswer
from .identifiers import AnswerId, CourseId, InteractionId, RunId, SessionId


class InteractionKind(StrEnum):
    HUMAN = "human"
    ASSISTANT = "assistant"
    NOTE = "note"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class InteractionRecord:
    id: InteractionId
    kind: InteractionKind
    occurred_at: datetime
    content: str
    answer_id: AnswerId | None = None
    run_id: RunId | None = None

    def __post_init__(self) -> None:
        require_aware(self.occurred_at, "occurred_at")
        require_text(self.content, "content")
        if self.kind is InteractionKind.ASSISTANT:
            if self.answer_id is None or self.run_id is None:
                raise ValueError("assistant interactions require answer_id and run_id")
        elif self.answer_id is not None or self.run_id is not None:
            raise ValueError("only assistant interactions may link an answer and run")


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    id: AnswerId
    interaction_id: InteractionId
    question_interaction_id: InteractionId
    run_id: RunId
    idempotency_key: str
    command_fingerprint: str
    answer: GroundedAnswer

    def __post_init__(self) -> None:
        if self.interaction_id == self.question_interaction_id:
            raise ValueError("answer and question interactions must be distinct")
        require_text(self.idempotency_key, "idempotency_key")
        _require_fingerprint(self.command_fingerprint, "command_fingerprint")
        if self.answer.provenance.playbook_run_id != self.run_id:
            raise ValueError("answer provenance run must match answer record run")


@dataclass(frozen=True, slots=True)
class SummaryExchange:
    question_interaction_id: InteractionId
    answer_interaction_id: InteractionId
    learner_excerpt: str
    assistant_excerpt: str
    answer_status: AnswerStatus
    unsupported_note: str | None = None

    def __post_init__(self) -> None:
        if self.question_interaction_id == self.answer_interaction_id:
            raise ValueError("summary exchange interaction ids must be distinct")
        require_text(self.learner_excerpt, "learner_excerpt")
        require_text(self.assistant_excerpt, "assistant_excerpt")
        if self.unsupported_note is not None:
            require_text(self.unsupported_note, "unsupported_note")
        if (
            self.answer_status is not AnswerStatus.ANSWERED
            and self.unsupported_note is None
        ):
            raise ValueError("non-answered summary exchanges require an unsupported note")


@dataclass(frozen=True, slots=True)
class ContinuationSummaryV1:
    through_interaction_id: InteractionId
    interaction_count: int
    recent_exchanges: tuple[SummaryExchange, ...]
    grounded_points: tuple[str, ...]
    unresolved_notes: tuple[str, ...]
    character_count: int
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "recent_exchanges", tuple(self.recent_exchanges))
        object.__setattr__(self, "grounded_points", tuple(self.grounded_points))
        object.__setattr__(self, "unresolved_notes", tuple(self.unresolved_notes))
        if self.schema_version != 1:
            raise ValueError("unsupported continuation summary schema version")
        if self.interaction_count < 1:
            raise ValueError("interaction_count must be positive")
        if not 0 <= self.character_count <= 2_000:
            raise ValueError("character_count must be between zero and 2000")
        if len(self.recent_exchanges) > 4:
            raise ValueError("recent_exchanges cannot contain more than four exchanges")
        exchange_ids = tuple(
            (item.question_interaction_id, item.answer_interaction_id)
            for item in self.recent_exchanges
        )
        if len(set(exchange_ids)) != len(exchange_ids):
            raise ValueError("recent_exchanges must have unique interaction linkages")
        for point in self.grounded_points:
            require_text(point, "grounded_points item")
        for note in self.unresolved_notes:
            require_text(note, "unresolved_notes item")
        if len(set(self.grounded_points)) != len(self.grounded_points):
            raise ValueError("grounded_points must be ordered and unique")
        if len(set(self.unresolved_notes)) != len(self.unresolved_notes):
            raise ValueError("unresolved_notes must be ordered and unique")
        actual_count = sum(
            len(exchange.learner_excerpt)
            + len(exchange.assistant_excerpt)
            + (len(exchange.unsupported_note) if exchange.unsupported_note is not None else 0)
            for exchange in self.recent_exchanges
        ) + sum(map(len, (*self.grounded_points, *self.unresolved_notes)))
        if self.character_count != actual_count:
            raise ValueError("character_count must match the canonical excerpts")


@dataclass(frozen=True, slots=True)
class StudySessionRecord:
    id: SessionId
    course_id: CourseId
    status: SessionStatus
    started_at: datetime
    suspended_at: datetime | None = None
    resumed_at: datetime | None = None
    ended_at: datetime | None = None
    interaction_ids: tuple[InteractionId, ...] = ()
    run_ids: tuple[RunId, ...] = ()
    continuation_summary: ContinuationSummaryV1 | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "interaction_ids", tuple(self.interaction_ids))
        object.__setattr__(self, "run_ids", tuple(self.run_ids))
        require_aware(self.started_at, "started_at")
        for name in ("suspended_at", "resumed_at", "ended_at"):
            value = getattr(self, name)
            if value is not None:
                require_aware(value, name)
                if value < self.started_at:
                    raise ValueError(f"{name} cannot precede started_at")
        if self.ended_at is not None:
            if self.status is not SessionStatus.ENDED:
                raise ValueError("ended_at requires ended status")
        elif self.status is SessionStatus.ENDED:
            raise ValueError("ended status requires ended_at")
        if self.status is SessionStatus.SUSPENDED and self.suspended_at is None:
            raise ValueError("suspended status requires suspended_at")
        if (
            self.status is SessionStatus.ACTIVE
            and self.resumed_at is not None
            and self.suspended_at is not None
            and self.resumed_at < self.suspended_at
        ):
            raise ValueError("active session resume cannot precede its latest suspension")
        if self.ended_at is not None:
            prior = tuple(
                item
                for item in (self.suspended_at, self.resumed_at)
                if item is not None
            )
            if prior and self.ended_at < max(prior):
                raise ValueError("ended_at cannot precede a lifecycle transition")
        if len(set(self.interaction_ids)) != len(self.interaction_ids):
            raise ValueError("interaction_ids must be unique")
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("run_ids must be unique")
        if self.continuation_summary is not None:
            if self.continuation_summary.through_interaction_id not in self.interaction_ids:
                raise ValueError("summary must link to an existing interaction")
            if self.continuation_summary.interaction_count != len(self.interaction_ids):
                raise ValueError("summary interaction_count must match canonical history")


# Pre-release compatibility alias. The record shape is now event-sourced.
StudySession = StudySessionRecord


def _require_fingerprint(value: str, name: str) -> None:
    require_text(value, name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")
