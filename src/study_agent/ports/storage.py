from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from study_agent.domain.events import DomainEvent, EventEnvelope
from study_agent.domain.identifiers import CourseId, RevisionId, RunId
from study_agent.domain.source import BlobRef, Citation, ResolvedCitation


class EventSequenceConflictError(RuntimeError):
    """Portable optimistic-concurrency conflict for a course event stream."""

    def __init__(self, course_id: CourseId, expected: int, actual: int) -> None:
        self.course_id = course_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"course {course_id} sequence conflict: expected {expected}, actual {actual}"
        )


class BlobStore(Protocol):
    def put(self, content: bytes) -> BlobRef: ...

    def get(self, ref: BlobRef) -> bytes: ...


class SourceContentPort(Protocol):
    def get_text(self, revision_id: RevisionId) -> str: ...

    def resolve(self, citation: Citation) -> ResolvedCitation: ...


type _EventRecord = DomainEvent | EventEnvelope


class EventStore(Protocol):
    """Canonical envelope-only event-store contract."""

    def append(
        self,
        stream_id: CourseId,
        expected_sequence: int,
        events: Sequence[EventEnvelope],
    ) -> int: ...

    def read(
        self, stream_id: CourseId, after_sequence: int = 0
    ) -> Sequence[EventEnvelope]: ...


class _LegacyEventStore(Protocol):
    """Private compatibility seam for legacy DomainEvent consumers."""

    def append(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[DomainEvent],
    ) -> int: ...

    def read(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[_EventRecord]: ...


@runtime_checkable
class _LegacyRecordReader(Protocol):
    """Optional private reader preserving legacy session metadata for replay."""

    def _read_records(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[_EventRecord]: ...


def _read_legacy(
    store: _LegacyEventStore, course_id: CourseId, after_sequence: int = 0
) -> tuple[_EventRecord, ...]:
    """Read private legacy records when an adapter provides that seam."""

    if isinstance(store, _LegacyRecordReader):
        return tuple(store._read_records(course_id, after_sequence))
    return tuple(store.read(course_id, after_sequence))


def _read_domain_events(
    store: _LegacyEventStore, course_id: CourseId, after_sequence: int = 0
) -> tuple[DomainEvent, ...]:
    """Read transitional records for legacy consumers without losing envelopes."""

    return tuple(
        event if isinstance(event, DomainEvent) else _envelope_to_legacy(event)
        for event in _read_legacy(store, course_id, after_sequence)
    )


def _envelope_to_legacy(event: EventEnvelope) -> DomainEvent:
    """Adapt a public envelope for a private legacy reducer seam."""

    return DomainEvent(
        event_id=event.event_id,
        course_id=event.stream_id,
        course_sequence=event.stream_sequence,
        event_type=event.event_type,
        schema_version=event.schema_version,
        actor=event.actor,
        occurred_at=event.occurred_at,
        correlation_id=event.correlation_id,
        payload=event.payload,
        causation_id=event.causation_id,
    )


class RunStore(Protocol):
    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool: ...

    def load(self, run_id: RunId) -> bytes: ...
