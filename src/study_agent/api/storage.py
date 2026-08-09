"""Curated envelope-only event and storage-port facade."""

from collections.abc import Sequence as _Sequence
from typing import Protocol as _Protocol

from study_agent.domain.events import Actor, EventEnvelope, PrincipalKind
from study_agent.domain.identifiers import CourseId as _CourseId
from study_agent.ports.storage import EventSequenceConflictError


class EventStore(_Protocol):
    """Public canonical event store; legacy DomainEvent is not in this API."""

    def append(
        self,
        stream_id: _CourseId,
        expected_sequence: int,
        events: _Sequence[EventEnvelope],
    ) -> int: ...

    def read(
        self, stream_id: _CourseId, after_sequence: int = 0
    ) -> _Sequence[EventEnvelope]: ...

__all__ = (
    "Actor",
    "EventEnvelope",
    "EventSequenceConflictError",
    "EventStore",
    "PrincipalKind",
)
