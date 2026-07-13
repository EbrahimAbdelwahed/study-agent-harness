"""Projection encoding and reduction for immutable source revisions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent
from study_agent.domain.source import BlobRef, SourceChunk, SourceDocument
from study_agent.state import EventRegistry

from .events import (
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    BlobLoader,
    PersistedChunkingConfig,
    SourceRevisionIngested,
    decode_source_revision_event,
)
from .identity import CHUNK_MAX_CHARACTERS, CHUNKER_POLICY_VERSION


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _blob(blob: BlobRef) -> JsonObject:
    return {
        "id": str(blob.id),
        "checksum_sha256": blob.checksum_sha256,
        "byte_length": blob.byte_length,
    }


def source_manifest(source: SourceDocument) -> JsonObject:
    return {
        "source_id": str(source.source_id),
        "revision_id": str(source.revision_id),
        "kind": source.kind.value,
        "title": source.title,
        "media_type": source.media_type,
        "checksum_sha256": source.checksum_sha256,
        "byte_length": source.byte_length,
        "created_at": _timestamp(source.created_at),
        "trust_level": source.trust_level,
        "source_role": source.source_role,
        "blob": _blob(source.blob),
        "normalized_blob": _blob(source.normalized_blob),
        "normalization_version": source.normalization_version,
        "normalized_character_length": source.normalized_character_length,
        "structure_origin": source.structure_origin.value,
        "ingestion_method": source.ingestion_method,
        "content_origin": source.content_origin.value,
    }


def chunk_manifest(chunk: SourceChunk) -> JsonObject:
    return {
        "chunk_id": str(chunk.chunk_id),
        "source_id": str(chunk.source_id),
        "revision_id": str(chunk.revision_id),
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "section_path": chunk.section_path,
        "ordinal": chunk.ordinal,
        "checksum_sha256": chunk.checksum_sha256,
        "chunker_version": chunk.chunker_version,
        "metadata": chunk.metadata,
    }


def source_revision_payload(
    source: SourceDocument,
    chunks: tuple[SourceChunk, ...],
    *,
    chunker_version: str = CHUNKER_POLICY_VERSION,
    max_characters: int = CHUNK_MAX_CHARACTERS,
) -> JsonObject:
    chunking = PersistedChunkingConfig(chunker_version, max_characters)
    decoded = SourceRevisionIngested(
        source, chunks, source.normalized_character_length, chunking
    )
    return {
        "source": source_manifest(decoded.source),
        "chunks": tuple(chunk_manifest(chunk) for chunk in decoded.chunks),
        "normalized_character_length": decoded.normalized_character_length,
        "chunking": {
            "version": decoded.chunking.version,
            "max_characters": decoded.chunking.max_characters,
        },
    }


def _mapping(value: JsonValue | None, name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise ValueError(f"projection field {name} must be an object")
    return value


def reduce_source_revision(
    state: JsonObject, _: DomainEvent, payload: SourceRevisionIngested
) -> Mapping[str, JsonValue]:
    sources = dict(_mapping(state.get("sources", {}), "sources"))
    chunks = dict(_mapping(state.get("chunks", {}), "chunks"))
    source_id = str(payload.source.source_id)
    revision_id = str(payload.source.revision_id)
    existing_source = dict(_mapping(sources.get(source_id, {}), f"sources.{source_id}"))
    revisions = dict(
        _mapping(existing_source.get("revisions", {}), f"sources.{source_id}.revisions")
    )
    revision_ids_value = existing_source.get("revision_ids", ())
    if not isinstance(revision_ids_value, tuple) or any(
        not isinstance(item, str) for item in revision_ids_value
    ):
        raise ValueError("source revision_ids projection field is invalid")
    revision_ids = cast(tuple[str, ...], revision_ids_value)
    manifest: JsonObject = {
        "source": source_manifest(payload.source),
        "normalized_character_length": payload.normalized_character_length,
        "chunking": {
            "version": payload.chunking.version,
            "max_characters": payload.chunking.max_characters,
        },
    }
    if revision_id in revisions:
        if revisions[revision_id] != manifest:
            raise ValueError("revision id already exists with different immutable metadata")
        existing_chunk_ids = {
            chunk_id
            for chunk_id, value in chunks.items()
            if isinstance(value, Mapping)
            and value.get("source_id") == source_id
            and value.get("revision_id") == revision_id
        }
        incoming_chunk_ids = {str(chunk.chunk_id) for chunk in payload.chunks}
        if existing_chunk_ids != incoming_chunk_ids:
            raise ValueError("revision id already exists with a different immutable chunk set")
    else:
        revisions[revision_id] = manifest
        revision_ids = (*revision_ids, revision_id)

    for chunk in payload.chunks:
        chunk_id = str(chunk.chunk_id)
        encoded = chunk_manifest(chunk)
        if chunk_id in chunks and chunks[chunk_id] != encoded:
            raise ValueError("chunk id already exists with different immutable metadata")
        chunks[chunk_id] = encoded

    sources[source_id] = {"revision_ids": revision_ids, "revisions": revisions}
    return {**state, "sources": sources, "chunks": chunks}


def register_source_revision_events(registry: EventRegistry, load_blob: BlobLoader) -> None:
    registry.register_event(
        SOURCE_REVISION_INGESTED,
        SOURCE_REVISION_SCHEMA_VERSION,
        lambda event: decode_source_revision_event(event, load_blob),
        reduce_source_revision,
    )
