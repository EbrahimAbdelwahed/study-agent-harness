from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from ._validation import JsonObject, freeze_object, require_aware, require_text
from .identifiers import CorrelationId, CourseId, EventId, SessionId


class PrincipalKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class Actor:
    kind: PrincipalKind
    principal_id: str

    def __post_init__(self) -> None:
        require_text(self.principal_id, "principal_id")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: EventId
    course_id: CourseId
    course_sequence: int
    event_type: str
    schema_version: int
    actor: Actor
    occurred_at: datetime
    correlation_id: CorrelationId
    payload: JsonObject = field(default_factory=dict)
    session_id: SessionId | None = None
    causation_id: EventId | None = None

    def __post_init__(self) -> None:
        if self.course_sequence < 1:
            raise ValueError("course_sequence must be positive")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        require_text(self.event_type, "event_type")
        require_aware(self.occurred_at, "occurred_at")
        if self.causation_id == self.event_id:
            raise ValueError("an event cannot cause itself")
        object.__setattr__(self, "payload", freeze_object(self.payload))
