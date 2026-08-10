from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from study_agent.domain.authority import IdempotencyKey
from study_agent.domain.errors import (
    ConflictFailure,
    NotFoundFailure,
    StaleFailure,
    ValidationFailure,
)
from study_agent.domain.events import DomainEvent, EventEnvelope
from study_agent.domain.identifiers import CourseId, RevisionId, RunId
from study_agent.domain.source import BlobRef, Citation, ResolvedCitation


class EventSequenceConflictError(StaleFailure):
    """Portable optimistic-concurrency conflict for a course event stream."""

    def __init__(self, course_id: CourseId, expected: int, actual: int) -> None:
        self.course_id = course_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            "the durable stream changed before commit",
            details={"stream_id": str(course_id), "expected": expected, "actual": actual},
        )


class IdempotencyConflictError(ConflictFailure):
    """A retry key was reused with different canonical command bytes."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__("idempotency key conflicts with a prior command")


class RunStoreConflictFailure(ConflictFailure):
    """An operational compare-and-set lost a race.

    The value is deliberately false-y so the historical boolean run-store
    consumers continue to branch safely while newer callers can inspect a
    typed conflict result.
    """

    def __bool__(self) -> bool:
        return False


class RunNotFoundError(NotFoundFailure, KeyError):
    """A requested operational record does not exist."""

    def __init__(self, run_id: RunId) -> None:
        self.run_id = run_id
        NotFoundFailure.__init__(self, "operational run was not found")
        KeyError.__init__(self, run_id)


@runtime_checkable
class BlobStore(Protocol):
    def put(self, content: bytes, ref: BlobRef | None = None) -> BlobRef: ...

    def get(self, ref: BlobRef) -> bytes: ...


class SourceContentPort(Protocol):
    def get_text(self, revision_id: RevisionId) -> str: ...

    def resolve(self, citation: Citation) -> ResolvedCitation: ...


type _EventRecord = DomainEvent | EventEnvelope


@dataclass(frozen=True, slots=True)
class CourseStreamHighWater:
    """The authoritative sequence observed for one course event stream."""

    course_id: CourseId
    sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.course_id, CourseId):
            raise ValidationFailure("course_id must be a CourseId")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValidationFailure("course stream high-water must be a non-negative integer")


@runtime_checkable
class CourseStreamHighWaterPort(Protocol):
    """Observe the sequence owned by a canonical course event stream."""

    def observe_high_water(self, course_id: CourseId) -> CourseStreamHighWater: ...


@runtime_checkable
class EventStore(Protocol):
    """Canonical envelope-only event-store contract."""

    def append(
        self,
        stream_id: CourseId,
        expected_sequence: int,
        events: Sequence[EventEnvelope],
        idempotency_key: IdempotencyKey | str,
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
class _LegacyEventAppender(Protocol):
    """Private no-key append seam retained for pre-PF04 reducers."""

    def _append_legacy(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[DomainEvent],
    ) -> int: ...


def _append_legacy(
    store: _LegacyEventStore,
    course_id: CourseId,
    expected_sequence: int,
    events: Sequence[DomainEvent],
) -> int:
    """Write legacy domain records through a private adapter seam.

    Test doubles that predate PF-04 still expose only ``append``; they remain
    usable while production adapters opt into the explicit private method.
    """

    if isinstance(store, _LegacyEventAppender):
        return store._append_legacy(course_id, expected_sequence, events)
    return store.append(course_id, expected_sequence, events)


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


@runtime_checkable
class RunStore(Protocol):
    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool | RunStoreConflictFailure: ...

    def load(self, run_id: RunId) -> bytes: ...


@runtime_checkable
class Repository(Protocol):
    """Host-composed storage bundle; it is not a second transaction owner."""

    @property
    def event_store(self) -> EventStore: ...

    @property
    def blob_store(self) -> BlobStore: ...

    @property
    def source_content(self) -> SourceContentPort | None: ...

    @property
    def run_store(self) -> RunStore: ...
