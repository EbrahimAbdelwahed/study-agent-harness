"""Projection encoding and reduction for immutable source revisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent
from study_agent.domain.identifiers import BlobId, SubstrateId
from study_agent.domain.source import BlobRef, MetadataAuthority, SourceChunk, SourceDocument
from study_agent.knowledge.scopes import register_scope_events
from study_agent.state import EventRegistry

from .events import (
    _CHUNK_KEYS,
    LEGACY_SOURCE_CREATED_AT,
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_INGESTED_V1,
    SOURCE_REVISION_SCHEMA_VERSION,
    SOURCE_REVISION_SELECTED,
    SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
    BlobLoader,
    PersistedChunkingConfig,
    SourceRevisionIngested,
    SourceRevisionSelected,
    _decode_historical_source_event,
    _validate_current_identity,
    decode_source_revision_ingested,
    decode_source_revision_ingested_v2,
    decode_source_revision_selected_event,
    upcast_source_revision_ingested_v1,
)
from .identity import CHUNK_MAX_CHARACTERS, CHUNKER_POLICY_VERSION
from .legacy import HistoricalIdentityVariant, classify_historical_identity
from .substrate_events import (
    SOURCE_SUBSTRATE_PRODUCED,
    SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
    decode_substrate_produced_event,
)
from .substrate_projection import reduce_substrate_produced
from .succession import (
    SOURCE_SUPERSEDED_BY,
    SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
    decode_source_superseded_by_event,
    reduce_source_superseded_by,
)


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
        "metadata_authority": source.metadata_authority.value,
    }


def source_event_manifest(source: SourceDocument) -> JsonObject:
    """Encode the current schema-2 source without its receipt timestamp."""

    manifest = dict(source_manifest(source))
    manifest.pop("created_at")
    return manifest


def source_manifest_v1(source: SourceDocument) -> JsonObject:
    """Encode the retained historical schema-1 source shape."""

    manifest = dict(source_manifest(source))
    manifest.pop("metadata_authority")
    return manifest


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
    decoded = SourceRevisionIngested(source, chunks, source.normalized_character_length, chunking)
    return {
        "source": source_event_manifest(decoded.source),
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


def _legacy_substrate_manifest(normalized_blob: BlobRef, character_length: int) -> JsonObject:
    """Return the bytes-only substrate view shared by v0.1 and v0.2."""
    return {
        "blob": _blob(normalized_blob),
        "character_length": character_length,
        "substrate_id": f"substrate:sha256:{normalized_blob.checksum_sha256}",
    }


def source_revision_payload_v1(
    source: SourceDocument,
    chunks: tuple[SourceChunk, ...],
    *,
    chunker_version: str = CHUNKER_POLICY_VERSION,
    max_characters: int = CHUNK_MAX_CHARACTERS,
) -> JsonObject:
    """Fixture/compatibility encoder for historical schema-1 events only."""

    chunking = PersistedChunkingConfig(chunker_version, max_characters)
    decoded = SourceRevisionIngested(source, chunks, source.normalized_character_length, chunking)
    return {
        "source": source_manifest_v1(decoded.source),
        "chunks": tuple(chunk_manifest(chunk) for chunk in decoded.chunks),
        "normalized_character_length": decoded.normalized_character_length,
        "chunking": {
            "version": decoded.chunking.version,
            "max_characters": decoded.chunking.max_characters,
        },
    }


def _projected_revision(
    source_value: JsonValue | None,
    revision_value: JsonValue | None,
    chunk_values: Sequence[JsonValue],
) -> SourceRevisionIngested:
    source = _mapping(source_value, "projected source")
    created_at = source.get("created_at")
    if not isinstance(created_at, str):
        raise ValueError("projected source created_at is invalid")
    timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("projected source created_at must be timezone-aware")
    revision = _mapping(revision_value, "projected revision")
    chunking = _mapping(revision.get("chunking"), "projected chunking")
    payload: JsonObject = {
        "source": {key: value for key, value in source.items() if key != "created_at"},
        "chunks": tuple(chunk_values),
        "normalized_character_length": revision.get("normalized_character_length"),
        "chunking": chunking,
    }
    return decode_source_revision_ingested(
        payload,
        receipt_created_at=timestamp.astimezone(UTC),
    )


def _source_projection_revisions(
    state: JsonObject,
) -> Mapping[tuple[str, str], SourceRevisionIngested]:
    sources = _mapping(state.get("sources", {}), "sources")
    chunks = _mapping(state.get("chunks", {}), "chunks")
    known_revision_keys: set[tuple[str, str]] = set()
    for source_id, source_value in sources.items():
        if type(source_id) is not str:
            raise ValueError("source projection key is invalid")
        source = _mapping(source_value, f"sources.{source_id}")
        if set(source) != {"revision_ids", "revisions", "current_revision_id"}:
            raise ValueError("source projection fields are invalid")
        revision_ids = source.get("revision_ids")
        revisions = _mapping(source.get("revisions"), f"sources.{source_id}.revisions")
        if not isinstance(revision_ids, tuple) or any(
            type(item) is not str for item in revision_ids
        ):
            raise ValueError("source revision history is invalid")
        if len(set(revision_ids)) != len(revision_ids) or set(revisions) != set(revision_ids):
            raise ValueError("source revision history is ambiguous")
        current = source.get("current_revision_id")
        if type(current) is not str or current not in revisions:
            raise ValueError("current source revision is invalid")
        typed_revision_ids = cast(tuple[str, ...], revision_ids)
        known_revision_keys.update(
            (source_id, revision_id) for revision_id in typed_revision_ids
        )

    for chunk_id, value in chunks.items():
        if type(chunk_id) is not str:
            raise ValueError("source projection chunk key is invalid")
        chunk = _mapping(value, f"chunks.{chunk_id}")
        if set(chunk) != set(_CHUNK_KEYS):
            raise ValueError("source projection chunk fields are invalid")
        if chunk.get("chunk_id") != chunk_id:
            raise ValueError("source projection chunk key does not match its identity")
        chunk_source_id = chunk.get("source_id")
        chunk_revision_id = chunk.get("revision_id")
        if type(chunk_source_id) is not str or type(chunk_revision_id) is not str:
            raise ValueError("source projection chunk ownership is invalid")
        if (chunk_source_id, chunk_revision_id) not in known_revision_keys:
            raise ValueError("source projection chunk ownership is unknown")

    result: dict[tuple[str, str], SourceRevisionIngested] = {}

    def chunk_ordinal(value: Mapping[str, JsonValue]) -> int:
        ordinal = value.get("ordinal")
        if type(ordinal) is not int:
            raise ValueError("source projection chunk ordinal is invalid")
        return ordinal

    for source_id, source_value in sources.items():
        if type(source_id) is not str:
            raise ValueError("source projection key is invalid")
        source = _mapping(source_value, f"sources.{source_id}")
        if set(source) != {"revision_ids", "revisions", "current_revision_id"}:
            raise ValueError("source projection fields are invalid")
        revision_ids = source.get("revision_ids")
        revisions = _mapping(source.get("revisions"), f"sources.{source_id}.revisions")
        if not isinstance(revision_ids, tuple) or any(
            type(item) is not str for item in revision_ids
        ):
            raise ValueError("source revision history is invalid")
        if len(set(revision_ids)) != len(revision_ids) or set(revisions) != set(revision_ids):
            raise ValueError("source revision history is ambiguous")
        current = source.get("current_revision_id")
        if type(current) is not str or current not in revisions:
            raise ValueError("current source revision is invalid")
        typed_revision_ids = cast(tuple[str, ...], revision_ids)
        consumed_chunk_ids: set[str] = set()
        for revision_id in typed_revision_ids:
            revision_value = revisions[revision_id]
            revision = _mapping(revision_value, f"sources.{source_id}.revisions.{revision_id}")
            raw_source = _mapping(revision.get("source"), "projected source")
            raw_source_id = raw_source.get("source_id")
            raw_revision_id = raw_source.get("revision_id")
            if raw_source_id != source_id or raw_revision_id != revision_id:
                raise ValueError("source revision projection is corrupt")
            revision_chunks = tuple(
                sorted(
                    (
                        value
                        for chunk_id, value in chunks.items()
                        if isinstance(value, Mapping)
                        and value.get("chunk_id") == chunk_id
                        and value.get("source_id") == source_id
                        and value.get("revision_id") == revision_id
                    ),
                    key=chunk_ordinal,
                )
            )
            consumed_chunk_ids.update(
                chunk_id
                for chunk_id, value in chunks.items()
                if type(chunk_id) is str
                and isinstance(value, Mapping)
                and value.get("chunk_id") == chunk_id
                and value.get("source_id") == source_id
                and value.get("revision_id") == revision_id
            )
            decoded = _projected_revision(raw_source, revision, revision_chunks)
            result[(source_id, revision_id)] = decoded
        projected_chunk_ids = {
            chunk_id
            for chunk_id, value in chunks.items()
            if type(chunk_id) is str
            and isinstance(value, Mapping)
            and value.get("source_id") == source_id
            and value.get("revision_id") in typed_revision_ids
            and value.get("chunk_id") == chunk_id
        }
        if consumed_chunk_ids != projected_chunk_ids:
            raise ValueError("source projection contains ambiguous chunk identities")
    all_chunk_ids = {
        chunk_id
        for chunk_id, value in chunks.items()
        if type(chunk_id) is str
        and isinstance(value, Mapping)
        and value.get("chunk_id") == chunk_id
    }
    consumed_ids = {
        str(chunk.chunk_id)
        for revision in result.values()
        for chunk in revision.chunks
    }
    if all_chunk_ids != consumed_ids:
        raise ValueError("source projection contains orphan chunks")
    return result


def normalize_historical_source_created_at(state: JsonObject) -> Mapping[str, JsonValue]:
    """Normalize retained v0.1 projection timestamps without rewriting events."""
    revisions = _source_projection_revisions(state)
    sources = _mapping(state.get("sources", {}), "sources")
    changed = False
    updated_sources = dict(sources)
    for (source_id, revision_id), decoded in revisions.items():
        source_projection = dict(
            _mapping(updated_sources[source_id], f"sources.{source_id}")
        )
        revision_projection = dict(
            _mapping(
                _mapping(source_projection["revisions"], "revisions")[revision_id],
                f"revisions.{revision_id}",
            )
        )
        source_manifest_value = _mapping(revision_projection["source"], "source")
        created_at_value = source_manifest_value.get("created_at")
        is_current = True
        try:
            _validate_current_identity(
                decoded.source,
                normalization_version=decoded.source.normalization_version,
            )
        except ValueError:
            is_current = False
        if is_current:
            if created_at_value != _timestamp(decoded.source.created_at):
                raise ValueError("current projected source timestamp is not canonical")
            continue
        # A replayed weak-v1 receipt has already quarantined its unbound
        # metadata. Keep the fixed sentinel form idempotent instead of trying
        # to classify it from metadata that was intentionally replaced.
        if (
            decoded.source.created_at == LEGACY_SOURCE_CREATED_AT
            and decoded.source.metadata_authority is MetadataAuthority.LEGACY_UNVERIFIED
            and decoded.source.title == "Legacy source"
            and decoded.source.trust_level == 0
            and decoded.source.source_role == "legacy-unverified"
        ):
            continue
        try:
            variant = classify_historical_identity(
                source=decoded.source,
                chunker_version=decoded.chunking.version,
                max_characters=decoded.chunking.max_characters,
            )
        except (TypeError, ValueError) as error:
            raise ValueError("projected source revision identity is unknown") from error
        if variant not in (
            HistoricalIdentityVariant.PUBLIC_MANIFEST,
            HistoricalIdentityVariant.INGESTION_V2,
            HistoricalIdentityVariant.WEAK_V01,
        ):
            raise ValueError("projected source revision identity is unsupported")
        source_manifest_value = dict(source_manifest_value)
        sentinel = "1970-01-01T00:00:00.000000Z"
        if source_manifest_value.get("created_at") != sentinel:
            source_manifest_value["created_at"] = sentinel
            revision_projection["source"] = source_manifest_value
            revisions_projection = dict(_mapping(source_projection["revisions"], "revisions"))
            revisions_projection[revision_id] = revision_projection
            source_projection["revisions"] = revisions_projection
            updated_sources[source_id] = source_projection
            changed = True
    if not changed:
        return state
    return {**state, "sources": updated_sources}


def validate_projected_source_receipts(
    state: JsonObject, events: Sequence[DomainEvent]
) -> Mapping[tuple[str, str], tuple[SourceRevisionIngested, datetime, int]]:
    """Validate projected source manifests against their exact event receipts."""
    projected = _source_projection_revisions(state)
    receipts: dict[tuple[str, str], tuple[SourceRevisionIngested, datetime, int]] = {}
    for event in events:
        if event.event_type != SOURCE_REVISION_INGESTED:
            continue
        if event.schema_version == SOURCE_REVISION_INGESTED_V1[1]:
            decoded_event = _decode_historical_source_event(event)
        elif event.schema_version == SOURCE_REVISION_SCHEMA_VERSION:
            decoded_event = decode_source_revision_ingested(
                event.payload, receipt_created_at=event.occurred_at
            )
            _validate_current_identity(
                decoded_event.source,
                normalization_version=decoded_event.source.normalization_version,
            )
        else:
            raise ValueError("unsupported source revision receipt schema")
        key = (str(decoded_event.source.source_id), str(decoded_event.source.revision_id))
        if key in receipts:
            raise ValueError("source revision receipt is ambiguous")
        projected_revision = projected.get(key)
        if projected_revision is None:
            raise ValueError("source revision projection is missing its receipt")
        if source_manifest(projected_revision.source) != source_manifest(decoded_event.source):
            raise ValueError("projected source manifest does not match its receipt")
        if projected_revision.chunks != decoded_event.chunks:
            raise ValueError("projected source chunks do not match their receipt")
        if projected_revision.chunking != decoded_event.chunking:
            raise ValueError("projected source chunking does not match its receipt")
        projected_at = projected_revision.source.created_at.astimezone(UTC)
        receipt_at = event.occurred_at.astimezone(UTC)
        if event.schema_version == SOURCE_REVISION_INGESTED_V1[1]:
            if projected_at != LEGACY_SOURCE_CREATED_AT:
                raise ValueError("historical projected source receipt was not normalized")
        elif projected_at != receipt_at:
            raise ValueError("current projected source receipt drifted")
        receipts[key] = (projected_revision, receipt_at, event.schema_version)
    if set(receipts) != set(projected):
        raise ValueError("source projection receipts are missing or orphaned")
    return receipts


def ensure_legacy_substrates(state: JsonObject) -> Mapping[str, JsonValue]:
    """Materialize legacy substrates in a persisted v0.1 projection.

    This migration is projection-only: the append-only event stream remains
    unchanged and the operation is deterministic from the existing source
    manifests.
    """
    sources = _mapping(state.get("sources", {}), "sources")
    substrates = dict(_mapping(state.get("substrates", {}), "substrates"))
    changed = False
    for source_id, source_value in sources.items():
        source = _mapping(source_value, f"sources.{source_id}")
        revisions = _mapping(source.get("revisions", {}), f"sources.{source_id}.revisions")
        for revision_id, revision_value in revisions.items():
            revision = _mapping(
                revision_value,
                f"sources.{source_id}.revisions.{revision_id}",
            )
            manifest = _mapping(
                revision.get("source"),
                f"sources.{source_id}.revisions.{revision_id}.source",
            )
            normalized = _mapping(
                manifest.get("normalized_blob"),
                "normalized_blob",
            )
            checksum = normalized.get("checksum_sha256")
            blob_id = normalized.get("id")
            byte_length = normalized.get("byte_length")
            character_length = revision.get("normalized_character_length")
            if (
                not isinstance(checksum, str)
                or not isinstance(blob_id, str)
                or blob_id != f"sha256:{checksum}"
                or type(byte_length) is not int
                or type(character_length) is not int
                or character_length < 1
            ):
                raise ValueError("legacy normalized blob manifest is invalid")
            substrate_ref = BlobRef(
                BlobId(blob_id),
                checksum,
                byte_length,
            )
            substrate_id = f"substrate:sha256:{checksum}"
            candidate = _legacy_substrate_manifest(substrate_ref, character_length)
            existing = substrates.get(substrate_id)
            if existing is not None and existing != candidate:
                raise ValueError("legacy substrate id already exists with different bytes")
            if existing is None:
                substrates[substrate_id] = candidate
                changed = True
    if not changed:
        return state
    return {**state, "substrates": substrates}


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

    sources[source_id] = {
        "revision_ids": revision_ids,
        "revisions": revisions,
        "current_revision_id": revision_id,
    }
    # v0.1 events remain untouched.  Their normalized blob is already a
    # verified canonical UTF-8 artifact, so the v0.2 substrate view can expose
    # a deterministic legacy mapping without emitting a second event.
    normalized_blob = payload.source.normalized_blob
    legacy_substrate_id = SubstrateId(f"substrate:sha256:{normalized_blob.checksum_sha256}")
    substrates = dict(_mapping(state.get("substrates", {}), "substrates"))
    substrate_key = str(legacy_substrate_id)
    legacy_manifest = _legacy_substrate_manifest(
        normalized_blob, payload.source.normalized_character_length
    )
    existing_legacy = substrates.get(substrate_key)
    if existing_legacy is not None and existing_legacy != legacy_manifest:
        raise ValueError("legacy substrate id already exists with different metadata")
    substrates[substrate_key] = legacy_manifest
    return {**state, "sources": sources, "chunks": chunks, "substrates": substrates}


def reduce_source_revision_selected(
    state: JsonObject, _: DomainEvent, payload: SourceRevisionSelected
) -> Mapping[str, JsonValue]:
    sources = dict(_mapping(state.get("sources", {}), "sources"))
    source_id = str(payload.source_id)
    revision_id = str(payload.revision_id)
    existing_source = dict(_mapping(sources.get(source_id, {}), f"sources.{source_id}"))
    revisions = _mapping(existing_source.get("revisions", {}), f"sources.{source_id}.revisions")
    if revision_id not in revisions:
        raise ValueError("selected revision must already exist for its source")
    revision_ids = existing_source.get("revision_ids", ())
    if not isinstance(revision_ids, tuple) or any(
        not isinstance(item, str) for item in revision_ids
    ):
        raise ValueError("source revision_ids projection field is invalid")
    if revision_id not in revision_ids:
        raise ValueError("selected revision must belong to immutable revision history")
    existing_source["current_revision_id"] = revision_id
    sources[source_id] = existing_source
    return {**state, "sources": sources}


def register_source_revision_events(registry: EventRegistry, load_blob: BlobLoader) -> None:
    registry.register_projection_migration(normalize_historical_source_created_at)
    registry.register_projection_migration(ensure_legacy_substrates)
    # The generic registry's payload upcaster cannot retain the original
    # envelope schema.  Keep historical verification on the explicit private
    # replay boundary instead of allowing a schema-1 payload to enter the
    # current append decoder through a caller-controlled marker.
    registry.register_event(
        SOURCE_REVISION_INGESTED,
        SOURCE_REVISION_INGESTED_V1[1],
        lambda event: upcast_source_revision_ingested_v1(event, load_blob),
        reduce_source_revision,
    )
    registry.register_event(
        SOURCE_REVISION_INGESTED,
        SOURCE_REVISION_SCHEMA_VERSION,
        lambda event: decode_source_revision_ingested_v2(event, load_blob),
        reduce_source_revision,
    )
    registry.register_event(
        SOURCE_REVISION_SELECTED,
        SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
        decode_source_revision_selected_event,
        reduce_source_revision_selected,
    )
    registry.register_event(
        SOURCE_SUBSTRATE_PRODUCED,
        SOURCE_SUBSTRATE_PRODUCED_SCHEMA_VERSION,
        lambda event: decode_substrate_produced_event(event, load_blob),
        reduce_substrate_produced,
    )
    registry.register_event(
        SOURCE_SUPERSEDED_BY,
        SOURCE_SUPERSEDED_BY_SCHEMA_VERSION,
        decode_source_superseded_by_event,
        reduce_source_superseded_by,
    )
    register_scope_events(registry)
