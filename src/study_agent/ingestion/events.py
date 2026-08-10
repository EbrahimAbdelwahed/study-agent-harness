"""Schema-discriminated source-revision events and replay validation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast

from study_agent.domain._validation import JsonObject, JsonValue
from study_agent.domain.events import DomainEvent
from study_agent.domain.identifiers import BlobId, ChunkId, RevisionId, SourceId
from study_agent.domain.provenance import ContentOrigin, StructureOrigin
from study_agent.domain.source import (
    BlobRef,
    MetadataAuthority,
    SourceChunk,
    SourceDocument,
    SourceKind,
)
from study_agent.domain.source_identity import (
    source_revision_id_for,
    source_revision_manifest,
)

from .chunking import CHUNKER_VERSION, ChunkingConfig, chunk_text
from .identity import (
    NORMALIZATION_POLICY_VERSION,
    chunk_id_for,
    source_kind_contract,
    source_revision_ingested_event_id_for,
    source_revision_selected_event_id_for,
)
from .legacy import (
    HistoricalIdentityVariant,
    classify_historical_identity,
    historical_source_event_id_for,
)
from .normalization import normalize_utf8

SOURCE_REVISION_INGESTED = "source.revision_ingested"
SOURCE_REVISION_INGESTED_V1 = (SOURCE_REVISION_INGESTED, 1)
SOURCE_REVISION_INGESTED_V2 = (SOURCE_REVISION_INGESTED, 2)
SOURCE_REVISION_SCHEMA_VERSION = 2
SOURCE_REVISION_SELECTED = "source.revision_selected"
SOURCE_REVISION_SELECTED_SCHEMA_VERSION = 1

_BLOB_KEYS = frozenset({"id", "checksum_sha256", "byte_length"})
_SOURCE_KEYS_V1 = frozenset(
    {
        "source_id",
        "revision_id",
        "kind",
        "title",
        "media_type",
        "checksum_sha256",
        "byte_length",
        "created_at",
        "trust_level",
        "source_role",
        "blob",
        "normalized_blob",
        "normalization_version",
        "normalized_character_length",
        "structure_origin",
        "ingestion_method",
        "content_origin",
    }
)
_SOURCE_KEYS_V2 = _SOURCE_KEYS_V1 - {"created_at"}
_SOURCE_KEYS_V2 = _SOURCE_KEYS_V2 | {"metadata_authority"}
_CHUNK_KEYS = frozenset(
    {
        "chunk_id",
        "source_id",
        "revision_id",
        "start_offset",
        "end_offset",
        "section_path",
        "ordinal",
        "checksum_sha256",
        "chunker_version",
        "metadata",
    }
)
_CHUNKING_KEYS = frozenset({"version", "max_characters"})

type BlobLoader = Callable[[BlobRef], bytes]


@dataclass(frozen=True, slots=True)
class PersistedChunkingConfig:
    version: str
    max_characters: int

    def __post_init__(self) -> None:
        if not self.version or self.version != self.version.strip():
            raise ValueError("chunking.version must be non-empty trimmed text")
        if type(self.max_characters) is not int or self.max_characters < 1:
            raise ValueError("chunking.max_characters must be positive")


@dataclass(frozen=True, slots=True)
class SourceRevisionIngested:
    source: SourceDocument
    chunks: tuple[SourceChunk, ...]
    normalized_character_length: int
    chunking: PersistedChunkingConfig

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunks", tuple(self.chunks))
        if type(self.normalized_character_length) is not int or (
            self.normalized_character_length < 1
        ):
            raise ValueError("normalized_character_length must be positive")
        if self.normalized_character_length != self.source.normalized_character_length:
            raise ValueError("normalized_character_length must match source manifest")
        _validate_chunks(
            self.source,
            self.chunks,
            self.normalized_character_length,
            self.chunking,
        )


@dataclass(frozen=True, slots=True)
class SourceRevisionSelected:
    source_id: SourceId
    revision_id: RevisionId


def source_revision_selected_payload(
    source_id: SourceId, revision_id: RevisionId
) -> JsonObject:
    return {"source_id": str(source_id), "revision_id": str(revision_id)}


def _object(value: JsonValue | None, name: str, keys: frozenset[str]) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    actual = frozenset(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")
    return value


def _text(value: JsonValue | None, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _integer(value: JsonValue | None, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _blob(value: JsonValue | None, name: str) -> BlobRef:
    payload = _object(value, name, _BLOB_KEYS)
    checksum = _text(payload.get("checksum_sha256"), f"{name}.checksum_sha256")
    blob_id = _text(payload.get("id"), f"{name}.id")
    if blob_id != f"sha256:{checksum}":
        raise ValueError(f"{name}.id must match its SHA-256 checksum")
    return BlobRef(
        BlobId(blob_id),
        checksum,
        _integer(payload.get("byte_length"), f"{name}.byte_length"),
    )


def _timestamp(value: JsonValue | None, name: str) -> datetime:
    text = _text(value, name)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return result.astimezone(UTC)


def _source(
    value: JsonValue | None,
    *,
    created_at: datetime | None,
    historical: bool,
) -> SourceDocument:
    keys = _SOURCE_KEYS_V1 if historical else _SOURCE_KEYS_V2
    payload = _object(value, "source", keys)
    try:
        kind = SourceKind(_text(payload.get("kind"), "source.kind"))
        structure_origin = StructureOrigin(
            _text(payload.get("structure_origin"), "source.structure_origin")
        )
        content_origin = ContentOrigin(
            _text(payload.get("content_origin"), "source.content_origin")
        )
        authority_value = payload.get("metadata_authority", MetadataAuthority.TRUSTED.value)
        authority = MetadataAuthority(_text(authority_value, "source.metadata_authority"))
    except ValueError as error:
        raise ValueError("source contains an unsupported enum value") from error
    if historical:
        timestamp = _timestamp(payload.get("created_at"), "source.created_at")
    else:
        if created_at is None or created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("source receipt timestamp must be timezone-aware")
        timestamp = created_at.astimezone(UTC)
    if timestamp is None:  # pragma: no cover - guarded by the current decoder
        raise ValueError("source receipt timestamp is required")
    return SourceDocument(
        source_id=SourceId(_text(payload.get("source_id"), "source.source_id")),
        revision_id=RevisionId(_text(payload.get("revision_id"), "source.revision_id")),
        kind=kind,
        title=_text(payload.get("title"), "source.title"),
        media_type=_text(payload.get("media_type"), "source.media_type"),
        checksum_sha256=_text(payload.get("checksum_sha256"), "source.checksum_sha256"),
        byte_length=_integer(payload.get("byte_length"), "source.byte_length"),
        created_at=timestamp,
        trust_level=_integer(payload.get("trust_level"), "source.trust_level"),
        source_role=_text(payload.get("source_role"), "source.source_role"),
        blob=_blob(payload.get("blob"), "source.blob"),
        normalized_blob=_blob(payload.get("normalized_blob"), "source.normalized_blob"),
        normalization_version=_text(
            payload.get("normalization_version"), "source.normalization_version"
        ),
        normalized_character_length=_integer(
            payload.get("normalized_character_length"),
            "source.normalized_character_length",
        ),
        structure_origin=structure_origin,
        ingestion_method=_text(payload.get("ingestion_method"), "source.ingestion_method"),
        content_origin=content_origin,
        metadata_authority=authority,
    )


def _chunk(value: JsonValue, index: int) -> SourceChunk:
    name = f"chunks[{index}]"
    payload = _object(value, name, _CHUNK_KEYS)
    section_path = payload.get("section_path")
    if not isinstance(section_path, tuple) or any(
        type(section) is not str for section in section_path
    ):
        raise ValueError(f"{name}.section_path must be an array of strings")
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError(f"{name}.metadata must be an object")
    return SourceChunk(
        chunk_id=ChunkId(_text(payload.get("chunk_id"), f"{name}.chunk_id")),
        source_id=SourceId(_text(payload.get("source_id"), f"{name}.source_id")),
        revision_id=RevisionId(_text(payload.get("revision_id"), f"{name}.revision_id")),
        start_offset=_integer(payload.get("start_offset"), f"{name}.start_offset"),
        end_offset=_integer(payload.get("end_offset"), f"{name}.end_offset"),
        section_path=cast(tuple[str, ...], section_path),
        ordinal=_integer(payload.get("ordinal"), f"{name}.ordinal"),
        checksum_sha256=_text(
            payload.get("checksum_sha256"), f"{name}.checksum_sha256"
        ),
        chunker_version=_text(payload.get("chunker_version"), f"{name}.chunker_version"),
        metadata=metadata,
    )


def _chunking(value: JsonValue | None) -> PersistedChunkingConfig:
    payload = _object(value, "chunking", _CHUNKING_KEYS)
    return PersistedChunkingConfig(
        _text(payload.get("version"), "chunking.version"),
        _integer(payload.get("max_characters"), "chunking.max_characters"),
    )


def _decode_payload(
    payload: JsonObject,
    *,
    receipt_created_at: datetime | None,
    historical: bool,
) -> SourceRevisionIngested:
    expected = {"source", "chunks", "normalized_character_length", "chunking"}
    if frozenset(payload) != expected:
        raise ValueError(
            "payload must contain exactly source, chunks, normalized_character_length, and chunking"
        )
    source = _source(payload.get("source"), created_at=receipt_created_at, historical=historical)
    chunks_value = payload.get("chunks")
    if not isinstance(chunks_value, tuple):
        raise ValueError("chunks must be an array")
    chunks = tuple(_chunk(value, index) for index, value in enumerate(chunks_value))
    return SourceRevisionIngested(
        source,
        chunks,
        _integer(payload.get("normalized_character_length"), "normalized_character_length"),
        _chunking(payload.get("chunking")),
    )


def decode_source_revision_ingested(
    payload: JsonObject, *, receipt_created_at: datetime | None = None
) -> SourceRevisionIngested:
    """Decode only the current payload shape, with an optional trusted receipt."""

    if receipt_created_at is None:
        raise ValueError("current source payload decoding requires a trusted receipt")
    return _decode_payload(
        payload,
        receipt_created_at=receipt_created_at,
        historical=False,
    )


def decode_source_revision_selected(payload: JsonObject) -> SourceRevisionSelected:
    decoded = _object(payload, "payload", frozenset({"source_id", "revision_id"}))
    return SourceRevisionSelected(
        SourceId(_text(decoded.get("source_id"), "source_id")),
        RevisionId(_text(decoded.get("revision_id"), "revision_id")),
    )


def decode_source_revision_selected_event(event: DomainEvent) -> SourceRevisionSelected:
    if (
        event.event_type != SOURCE_REVISION_SELECTED
        or event.schema_version != SOURCE_REVISION_SELECTED_SCHEMA_VERSION
    ):
        raise ValueError("event envelope does not match source.revision_selected@1")
    decoded = decode_source_revision_selected(event.payload)
    expected_id = source_revision_selected_event_id_for(
        event.course_id,
        decoded.source_id,
        decoded.revision_id,
        event.course_sequence,
    )
    if event.event_id != expected_id:
        raise ValueError("event_id does not match revision selection identity")
    return decoded


def _validate_chunks(
    source: SourceDocument,
    chunks: tuple[SourceChunk, ...],
    normalized_character_length: int,
    chunking: PersistedChunkingConfig,
) -> None:
    if not chunks:
        raise ValueError("chunks must contain at least one chunk")
    chunk_ids: set[ChunkId] = set()
    previous_end = 0
    for expected_ordinal, chunk in enumerate(chunks):
        if chunk.source_id != source.source_id or chunk.revision_id != source.revision_id:
            raise ValueError("every chunk must belong to the decoded source revision")
        if chunk.chunk_id in chunk_ids:
            raise ValueError("chunk ids must be unique within a revision")
        if chunk.ordinal != expected_ordinal:
            raise ValueError("chunk ordinals must be contiguous and start at zero")
        if chunk.start_offset < previous_end:
            raise ValueError("chunk spans must be ordered and non-overlapping")
        if chunk.end_offset > normalized_character_length:
            raise ValueError("chunk span exceeds normalized character length")
        if chunk.chunker_version != chunking.version:
            raise ValueError("chunk version must match persisted chunking config")
        chunk_ids.add(chunk.chunk_id)
        previous_end = chunk.end_offset


def _validate_current_identity(
    source: SourceDocument, *, normalization_version: str
) -> None:
    if source.metadata_authority is not MetadataAuthority.TRUSTED:
        raise ValueError("current source revisions require trusted metadata")
    expected = source_revision_id_for(
        source_revision_manifest(
            source_id=source.source_id,
            blob=source.blob,
            media_type=source.media_type,
            normalization_version=normalization_version,
            substrate_id=source.substrate_id,
            metadata={
                "kind": source.kind.value,
                "source_role": source.source_role,
                "title": source.title,
                "trust_level": source.trust_level,
            },
        )
    )
    if source.revision_id != expected:
        raise ValueError("revision_id does not match the v3 source manifest")


def _verified_blob(load_blob: BlobLoader, ref: BlobRef, name: str) -> bytes:
    if str(ref.id) != f"sha256:{ref.checksum_sha256}":
        raise ValueError(f"{name} id does not match its checksum")
    try:
        content = load_blob(ref)
    except KeyError as error:
        raise ValueError(f"{name} blob is unavailable") from error
    except Exception as error:
        raise ValueError(f"{name} blob loader failed") from error
    if type(content) is not bytes:
        raise ValueError(f"{name} loader must return bytes")
    if len(content) != ref.byte_length:
        raise ValueError(f"{name} byte length does not match loaded content")
    if sha256(content).hexdigest() != ref.checksum_sha256:
        raise ValueError(f"{name} checksum does not match loaded content")
    return content


def _verify_content(
    decoded: SourceRevisionIngested,
    event: DomainEvent,
    load_blob: BlobLoader,
) -> None:
    source = decoded.source
    original = _verified_blob(load_blob, source.blob, "source.blob")
    normalized_bytes = _verified_blob(load_blob, source.normalized_blob, "source.normalized_blob")
    try:
        normalized_text = normalized_bytes.decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise ValueError("normalized blob must contain strict UTF-8") from error
    if normalize_utf8(normalized_bytes).content != normalized_bytes:
        raise ValueError("normalized blob is not canonical newline-normalized NFC text")
    try:
        expected_normalized = normalize_utf8(original).content
    except ValueError as error:
        raise ValueError("original blob must contain strict UTF-8") from error
    if normalized_bytes != expected_normalized:
        raise ValueError("normalized blob does not match canonical normalization of original")
    if decoded.normalized_character_length != len(normalized_text):
        raise ValueError("normalized_character_length does not match normalized text")
    if source.normalization_version != NORMALIZATION_POLICY_VERSION:
        raise ValueError("unsupported normalization version")
    if decoded.chunking.version != CHUNKER_VERSION:
        raise ValueError("unsupported chunking version")
    expected_media_type, expected_method = source_kind_contract(source.kind)
    if source.media_type != expected_media_type or source.ingestion_method != expected_method:
        raise ValueError("source kind, media type, and ingestion method are inconsistent")
    if source.content_origin is not ContentOrigin.ORIGINAL:
        raise ValueError("ingested source content_origin must be original")
    if source.structure_origin is not StructureOrigin.MECHANICALLY_EXTRACTED:
        raise ValueError("ingested source structure_origin must be mechanically_extracted")
    if source.created_at != event.occurred_at.astimezone(UTC):
        raise ValueError("source.created_at must equal the event receipt")
    for chunk in decoded.chunks:
        span = normalized_text[chunk.start_offset : chunk.end_offset]
        digest = sha256(span.encode("utf-8")).hexdigest()
        if chunk.checksum_sha256 != digest:
            raise ValueError("chunk checksum does not match normalized text span")
        expected_chunk = chunk_id_for(
            source_id=chunk.source_id,
            revision_id=chunk.revision_id,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            checksum_sha256=chunk.checksum_sha256,
            chunker_version=chunk.chunker_version,
        )
        if chunk.chunk_id != expected_chunk:
            raise ValueError("chunk_id does not match canonical span identity")
    reconstructed = chunk_text(
        normalized_text,
        source_id=source.source_id,
        revision_id=source.revision_id,
        kind=source.kind,
        config=ChunkingConfig(
            max_characters=decoded.chunking.max_characters,
            version=decoded.chunking.version,
        ),
    )
    if decoded.chunks != reconstructed:
        raise ValueError("supplied chunks do not exactly match canonical chunking output")


def decode_source_revision_ingested_v2(
    event: DomainEvent, load_blob: BlobLoader
) -> SourceRevisionIngested:
    if (event.event_type, event.schema_version) != SOURCE_REVISION_INGESTED_V2:
        raise ValueError("event envelope does not match source.revision_ingested@2")
    decoded = decode_source_revision_ingested(
        event.payload, receipt_created_at=event.occurred_at
    )
    _validate_current_identity(
        decoded.source, normalization_version=decoded.source.normalization_version
    )
    _verify_content(decoded, event, load_blob)
    if event.event_id != source_revision_ingested_event_id_for(
        event.course_id, decoded.source.revision_id, event.occurred_at
    ):
        raise ValueError("event_id does not match v2 receipt identity")
    return decoded


def upcast_source_revision_ingested_v1(
    event: DomainEvent, load_blob: BlobLoader
) -> SourceRevisionIngested:
    """Verify and deterministically project one historical schema-1 event."""

    if (event.event_type, event.schema_version) != SOURCE_REVISION_INGESTED_V1:
        raise ValueError("event envelope does not match source.revision_ingested@1")
    decoded = _decode_payload(event.payload, receipt_created_at=None, historical=True)
    if decoded.source.created_at != event.occurred_at.astimezone(UTC):
        raise ValueError("historical source.created_at must equal its event receipt")
    variant = classify_historical_identity(
        source=decoded.source,
        chunker_version=decoded.chunking.version,
        max_characters=decoded.chunking.max_characters,
    )
    _verify_content(decoded, event, load_blob)
    if event.event_id != historical_source_event_id_for(
        event.course_id, decoded.source.revision_id
    ):
        raise ValueError("historical event_id does not match its preserved identity")
    if variant is HistoricalIdentityVariant.WEAK_V01:
        decoded = replace(
            decoded,
            source=replace(
                decoded.source,
                title="Legacy source",
                trust_level=0,
                source_role="legacy-unverified",
                metadata_authority=MetadataAuthority.LEGACY_UNVERIFIED,
            ),
        )
    return decoded


def prepare_for_append(event: DomainEvent, load_blob: BlobLoader) -> SourceRevisionIngested:
    """Append boundary: schema 2 only, with no legacy fallback."""

    if (event.event_type, event.schema_version) != SOURCE_REVISION_INGESTED_V2:
        raise ValueError("source revision append requires schema 2")
    return decode_source_revision_ingested_v2(event, load_blob)


def prepare_for_replay(event: DomainEvent, load_blob: BlobLoader) -> SourceRevisionIngested:
    """Replay boundary: explicitly dispatch the retained historical schema."""

    if (event.event_type, event.schema_version) == SOURCE_REVISION_INGESTED_V1:
        return upcast_source_revision_ingested_v1(event, load_blob)
    if (event.event_type, event.schema_version) == SOURCE_REVISION_INGESTED_V2:
        return decode_source_revision_ingested_v2(event, load_blob)
    raise ValueError("unsupported source revision event schema")


def decode_source_revision_event(
    event: DomainEvent, load_blob: BlobLoader
) -> SourceRevisionIngested:
    """Compatibility spelling for replay callers with explicit schema dispatch."""

    return prepare_for_replay(event, load_blob)


__all__ = [
    "SOURCE_REVISION_INGESTED",
    "SOURCE_REVISION_INGESTED_V1",
    "SOURCE_REVISION_INGESTED_V2",
    "SOURCE_REVISION_SCHEMA_VERSION",
    "SOURCE_REVISION_SELECTED",
    "SOURCE_REVISION_SELECTED_SCHEMA_VERSION",
    "BlobLoader",
    "PersistedChunkingConfig",
    "SourceRevisionIngested",
    "SourceRevisionSelected",
    "decode_source_revision_event",
    "decode_source_revision_ingested",
    "decode_source_revision_ingested_v2",
    "decode_source_revision_selected",
    "decode_source_revision_selected_event",
    "prepare_for_append",
    "prepare_for_replay",
    "source_revision_selected_payload",
    "upcast_source_revision_ingested_v1",
]
