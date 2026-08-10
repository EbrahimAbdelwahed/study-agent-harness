"""Canonical ingestion policy and deterministic identity helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from study_agent.domain.bounded_json import canonical_json_bytes
from study_agent.domain.identifiers import (
    ChunkId,
    CourseId,
    EventId,
    RevisionId,
    SourceId,
)
from study_agent.domain.source import SourceKind

NORMALIZATION_POLICY_VERSION = "utf8-newlines-nfc-v1"
CHUNKER_POLICY_VERSION = "heading-paragraph-v1"
CHUNK_MAX_CHARACTERS = 1200
TEXT_MEDIA_TYPE = "text/plain"
MARKDOWN_MEDIA_TYPE = "text/markdown"
TEXT_INGESTION_METHOD = "utf8-text-v1"
MARKDOWN_INGESTION_METHOD = "utf8-markdown-v1"


def source_kind_contract(kind: SourceKind) -> tuple[str, str]:
    if kind is SourceKind.TEXT:
        return TEXT_MEDIA_TYPE, TEXT_INGESTION_METHOD
    return MARKDOWN_MEDIA_TYPE, MARKDOWN_INGESTION_METHOD


def revision_id_for(
    *,
    original_sha256: str,
    source_id: SourceId,
    kind: SourceKind,
    title: str,
    trust_level: int,
    source_role: str,
    normalization_version: str,
    chunker_version: str,
    max_characters: int,
) -> RevisionId:
    """Compatibility helper for historical ingestion-v2 fixtures only.

    Current ingestion calls ``SourceRevision.create``.  This helper remains so
    old event fixtures can still construct the historical identity that the v1
    replay upcaster classifies.
    """

    manifest = {
        "chunker_version": chunker_version,
        "kind": kind.value,
        "max_characters": max_characters,
        "normalization_version": normalization_version,
        "original_sha256": original_sha256,
        "source_id": str(source_id),
        "source_role": source_role,
        "title": title,
        "trust_level": trust_level,
    }
    # This is intentionally the old v2 compatibility domain, never a current
    # append path.  The historical helper itself lives in ingestion.legacy;
    # this import-compatible wrapper is retained for pre-existing fixtures.
    return RevisionId(
        "revision-sha256:"
        + sha256(
            b"study-agent-source-revision-v2\0" + canonical_json_bytes(manifest)
        ).hexdigest()
    )


def chunk_id_for(
    *,
    source_id: SourceId,
    revision_id: RevisionId,
    start_offset: int,
    end_offset: int,
    checksum_sha256: str,
    chunker_version: str,
) -> ChunkId:
    identity = (
        f"{source_id}\0{revision_id}\0{start_offset}\0{end_offset}\0"
        f"{checksum_sha256}\0{chunker_version}"
    ).encode()
    return ChunkId(f"chunk-sha256:{sha256(identity).hexdigest()}")


def source_event_id_for(course_id: CourseId, revision_id: RevisionId) -> EventId:
    identity = f"{course_id}\0{revision_id}".encode()
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")


def source_revision_ingested_event_id_for(
    course_id: CourseId, revision_id: RevisionId, occurred_at: datetime
) -> EventId:
    """Authenticate the v2 capture receipt, including its UTC timestamp."""

    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")
    receipt = occurred_at.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
    identity = b"study-agent/source-revision-ingested/v2\0" + canonical_json_bytes(
        {
            "course_id": str(course_id),
            "occurred_at": receipt,
            "revision_id": str(revision_id),
        }
    )
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")


def source_revision_selected_event_id_for(
    course_id: CourseId,
    source_id: SourceId,
    revision_id: RevisionId,
    course_sequence: int,
) -> EventId:
    """Identify a current-revision transition at one canonical stream position."""

    identity = b"study-agent-source-revision-selected-v1\0" + canonical_json_bytes(
        {
            "course_id": str(course_id),
            "course_sequence": course_sequence,
            "revision_id": str(revision_id),
            "source_id": str(source_id),
        }
    )
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")


def source_superseded_by_event_id_for(
    course_id: CourseId,
    predecessor_source_id: SourceId,
    predecessor_revision_id: RevisionId,
    successor_source_id: SourceId,
    successor_revision_id: RevisionId,
    course_sequence: int,
) -> EventId:
    """Identify one explicit succession at a canonical stream position."""

    identity = b"study-agent-source-superseded-by-v1\0" + canonical_json_bytes(
        {
            "course_id": str(course_id),
            "course_sequence": course_sequence,
            "predecessor_revision_id": str(predecessor_revision_id),
            "predecessor_source_id": str(predecessor_source_id),
            "successor_revision_id": str(successor_revision_id),
            "successor_source_id": str(successor_source_id),
        }
    )
    return EventId(f"event-sha256:{sha256(identity).hexdigest()}")
