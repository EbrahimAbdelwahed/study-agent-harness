from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from study_agent.domain.events import DomainEvent
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
    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int: ...

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]: ...


class RunStore(Protocol):
    def create(self, run_id: RunId, payload: bytes) -> bool: ...

    def compare_and_set(
        self, run_id: RunId, expected: bytes, replacement: bytes
    ) -> bool: ...

    def load(self, run_id: RunId) -> bytes: ...
