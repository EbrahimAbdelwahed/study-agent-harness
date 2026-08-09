from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from study_agent.domain.events import EventEnvelope
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


class EventStore(Protocol):
    """Private compatibility seam for pre-envelope domain consumers.

    The curated API publishes an envelope-only protocol.  Internal services
    still accept this deliberately erased adapter while legacy DomainEvent
    reducers are migrated; no DomainEvent symbol is exported through the API.
    """

    def append(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[Any],
    ) -> int: ...

    def read(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[Any]: ...


class CanonicalEventStore(Protocol):
    """Envelope-only store contract used by the curated facade."""

    def append(
        self,
        stream_id: CourseId,
        expected_sequence: int,
        events: Sequence[EventEnvelope],
    ) -> int: ...

    def read(
        self, stream_id: CourseId, after_sequence: int = 0
    ) -> Sequence[EventEnvelope]: ...


class RunStore(Protocol):
    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool: ...

    def load(self, run_id: RunId) -> bytes: ...
