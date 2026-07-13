"""Canonical v0.1 ingestion policy and deterministic identity helpers."""

from __future__ import annotations

from hashlib import sha256

from study_agent.domain.identifiers import ChunkId, CourseId, EventId, RevisionId, SourceId
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
    """Identify immutable content/config; descriptive source metadata is excluded."""

    del title, trust_level, source_role
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
