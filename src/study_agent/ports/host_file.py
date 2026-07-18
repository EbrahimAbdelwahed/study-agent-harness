"""Trusted-host protocols for bounded, opaque file snapshots."""

from __future__ import annotations

from typing import Protocol

from study_agent.domain.context import ExecutionContext
from study_agent.domain.identifiers import CourseId, SessionId, SourceId


class HostFileIdentityPort(Protocol):
    """Issue an opaque identity for one exact trusted declaration."""

    def issue(
        self,
        course_id: CourseId,
        session_id: SessionId,
        checksum: str,
        declaration_fingerprint: str,
    ) -> str: ...


class HostFileSnapshotStore(Protocol):
    """Store canonical operational snapshot bytes, never domain events."""

    def create(self, file_id: str, payload: bytes) -> bool: ...

    def load(self, file_id: str) -> bytes: ...


class HostFileIngestionPort(Protocol):
    """Structural port matching the trusted text-ingestion keyword contract."""

    def ingest(
        self,
        *,
        filename: str,
        content: bytes,
        source_id: SourceId,
        title: str,
        trust_level: int,
        source_role: str,
        context: ExecutionContext,
        expected_sequence: int | None = None,
    ) -> object: ...


__all__ = [
    "HostFileIdentityPort",
    "HostFileIngestionPort",
    "HostFileSnapshotStore",
]
