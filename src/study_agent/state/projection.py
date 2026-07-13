"""Pure projection reduction over ordered per-course event streams."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from study_agent.domain._validation import JsonObject, freeze_object
from study_agent.domain.events import DomainEvent
from study_agent.domain.identifiers import CourseId

from .registry import EventRegistry
from .serialization import canonical_json_bytes


class ProjectionSequenceError(ValueError):
    """Raised when an event stream is not contiguous for its projection."""


@dataclass(frozen=True, slots=True)
class Projection:
    course_id: CourseId
    sequence: int = 0
    state: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("projection sequence cannot be negative")
        object.__setattr__(self, "state", freeze_object(self.state))

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(
            {"course_id": str(self.course_id), "sequence": self.sequence, "state": self.state}
        )


def apply_event(
    projection: Projection, event: DomainEvent, registry: EventRegistry
) -> Projection:
    """Return a new projection without mutating the prior projection or event."""
    expected = projection.sequence + 1
    if event.course_id != projection.course_id:
        raise ProjectionSequenceError("event course does not match projection course")
    if event.course_sequence != expected:
        raise ProjectionSequenceError(
            f"expected event sequence {expected}, got {event.course_sequence}"
        )
    next_state = registry.reduce(projection.state, event)
    return Projection(event.course_id, event.course_sequence, next_state)


def replay(
    course_id: CourseId, events: Sequence[DomainEvent], registry: EventRegistry
) -> Projection:
    projection = Projection(course_id)
    for event in events:
        projection = apply_event(projection, event, registry)
    return projection
