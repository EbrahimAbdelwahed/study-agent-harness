"""Canonical v0.1 ingestion policy and deterministic identity helpers."""

from __future__ import annotations

from hashlib import sha256

from study_agent.domain.identifiers import ChunkId, CourseId, EventId, RevisionId, SourceId
from study_agent.domain.source import SourceKind
from study_agent.state import canonical_json_bytes

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
    """Identify immutable content, metadata, and processing configuration (v2)."""

    identity = b"study-agent-source-revision-v2\0" + canonical_json_bytes(
        {
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
    )
    return RevisionId(f"revision-sha256:{sha256(identity).hexdigest()}")


def legacy_revision_id_for(
    *,
    original_sha256: str,
    source_id: SourceId,
    kind: SourceKind,
    normalization_version: str,
    chunker_version: str,
    max_characters: int,
) -> RevisionId:
    """Reconstruct the v0.1 identity used before metadata became revision-bearing."""

    identity = (
        f"{source_id}\0{original_sha256}\0{kind.value}\0{normalization_version}\0"
        f"{chunker_version}\0{max_characters}"
    ).encode()
    return RevisionId(f"revision-sha256:{sha256(identity).hexdigest()}")


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
