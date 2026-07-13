"""Application service for immutable text and Markdown source revisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import PurePath

from study_agent.domain.context import ExecutionContext
from study_agent.domain.events import Actor, DomainEvent
from study_agent.domain.identifiers import BlobId, RevisionId, SourceId
from study_agent.domain.provenance import ContentOrigin, StructureOrigin
from study_agent.domain.source import BlobRef, SourceChunk, SourceDocument, SourceKind
from study_agent.ports import BlobStore, ClockPort, CourseViewPort, EventStore
from study_agent.ports.storage import EventSequenceConflictError

from .chunking import CHUNKER_VERSION, DEFAULT_CHUNKING_CONFIG, ChunkingConfig, chunk_text
from .events import (
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    SourceRevisionIngested,
    decode_source_revision_ingested,
)
from .identity import revision_id_for, source_event_id_for, source_kind_contract
from .normalization import InvalidUtf8Error, normalize_utf8
from .projection import source_revision_payload


class IngestionErrorCode(StrEnum):
    UNSUPPORTED_EXTENSION = "unsupported_extension"
    INVALID_UTF8 = "invalid_utf8"
    INVALID_CONTENT = "invalid_content"
    SEQUENCE_CONFLICT = "sequence_conflict"
    BLOB_MISMATCH = "blob_mismatch"
    UNSUPPORTED_CONFIGURATION = "unsupported_configuration"


class IngestionStatus(StrEnum):
    EMITTED = "emitted"
    IDEMPOTENT = "idempotent"


class TextIngestionError(Exception):
    def __init__(self, code: IngestionErrorCode, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class TextIngestionResult:
    status: IngestionStatus
    source: SourceDocument
    chunks: tuple[SourceChunk, ...]
    committed_sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunks", tuple(self.chunks))


class TextIngestionService:
    def __init__(
        self,
        *,
        blobs: BlobStore,
        events: EventStore,
        clock: ClockPort,
        courses: CourseViewPort,
        chunking: ChunkingConfig = DEFAULT_CHUNKING_CONFIG,
    ) -> None:
        self._blobs = blobs
        self._events = events
        self._clock = clock
        self._courses = courses
        self._chunking = chunking

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
    ) -> TextIngestionResult:
        self._courses.get(context.course_id)
        if self._chunking.version != CHUNKER_VERSION:
            raise TextIngestionError(
                IngestionErrorCode.UNSUPPORTED_CONFIGURATION,
                f"unsupported chunker version: {self._chunking.version}",
            )
        kind, media_type, method = _file_contract(filename)
        try:
            normalized = normalize_utf8(content)
        except InvalidUtf8Error as error:
            raise TextIngestionError(IngestionErrorCode.INVALID_UTF8, str(error)) from error

        original_blob = _predicted_blob(content)
        normalized_blob = _predicted_blob(normalized.content)
        revision_id = revision_id_for(
            original_sha256=original_blob.checksum_sha256,
            source_id=source_id,
            kind=kind,
            title=title,
            trust_level=trust_level,
            source_role=source_role,
            normalization_version=normalized.version,
            chunker_version=self._chunking.version,
            max_characters=self._chunking.max_characters,
        )
        now = self._clock.now()
        try:
            source = SourceDocument(
                source_id,
                revision_id,
                kind,
                title,
                media_type,
                original_blob.checksum_sha256,
                original_blob.byte_length,
                now,
                trust_level,
                source_role,
                original_blob,
                normalized_blob,
                normalized.version,
                len(normalized.text),
                StructureOrigin.MECHANICALLY_EXTRACTED,
                method,
                ContentOrigin.ORIGINAL,
            )
            chunks = chunk_text(
                normalized.text,
                source_id=source_id,
                revision_id=revision_id,
                kind=kind,
                config=self._chunking,
            )
        except ValueError as error:
            raise TextIngestionError(IngestionErrorCode.INVALID_CONTENT, str(error)) from error

        stream = tuple(self._events.read(context.course_id))
        existing = _find_revision(stream, source_id, revision_id)
        current_sequence = stream[-1].course_sequence if stream else 0
        if existing is not None:
            return TextIngestionResult(
                IngestionStatus.IDEMPOTENT,
                existing.source,
                existing.chunks,
                current_sequence,
            )

        try:
            payload = source_revision_payload(
                source,
                chunks,
                chunker_version=self._chunking.version,
                max_characters=self._chunking.max_characters,
            )
            decoded = decode_source_revision_ingested(payload)
            if decoded.source != source or decoded.chunks != chunks:
                raise ValueError("typed event payload changed immutable source data")
            if decoded.normalized_character_length != len(normalized.text):
                raise ValueError("typed event payload changed normalized length")
            if (
                decoded.chunking.version != self._chunking.version
                or decoded.chunking.max_characters != self._chunking.max_characters
            ):
                raise ValueError("typed event payload changed chunking configuration")
            event = DomainEvent(
                source_event_id_for(context.course_id, revision_id),
                context.course_id,
                current_sequence + 1,
                SOURCE_REVISION_INGESTED,
                SOURCE_REVISION_SCHEMA_VERSION,
                Actor(context.principal_kind, context.principal_id),
                now,
                context.correlation_id,
                payload,
                session_id=context.session_id,
            )
        except ValueError as error:
            raise TextIngestionError(IngestionErrorCode.INVALID_CONTENT, str(error)) from error

        _write_expected_blob(self._blobs, content, original_blob)
        _write_expected_blob(self._blobs, normalized.content, normalized_blob)
        try:
            committed = self._events.append(context.course_id, current_sequence, (event,))
        except EventSequenceConflictError as error:
            concurrent_stream = tuple(self._events.read(context.course_id))
            concurrent = _find_revision(concurrent_stream, source_id, revision_id)
            if concurrent is not None:
                concurrent_sequence = (
                    concurrent_stream[-1].course_sequence if concurrent_stream else 0
                )
                return TextIngestionResult(
                    IngestionStatus.IDEMPOTENT,
                    concurrent.source,
                    concurrent.chunks,
                    concurrent_sequence,
                )
            raise TextIngestionError(
                IngestionErrorCode.SEQUENCE_CONFLICT,
                "course event sequence changed during ingestion",
                retryable=True,
            ) from error
        return TextIngestionResult(IngestionStatus.EMITTED, source, chunks, committed)


def _file_contract(filename: str) -> tuple[SourceKind, str, str]:
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".txt":
        media_type, method = source_kind_contract(SourceKind.TEXT)
        return SourceKind.TEXT, media_type, method
    if suffix == ".md":
        media_type, method = source_kind_contract(SourceKind.MARKDOWN)
        return SourceKind.MARKDOWN, media_type, method
    raise TextIngestionError(
        IngestionErrorCode.UNSUPPORTED_EXTENSION,
        "only .txt and .md files are supported",
    )


def _predicted_blob(content: bytes) -> BlobRef:
    digest = sha256(content).hexdigest()
    return BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))


def _write_expected_blob(store: BlobStore, content: bytes, expected: BlobRef) -> None:
    try:
        actual = store.put(content)
    except (TypeError, ValueError) as error:
        raise TextIngestionError(IngestionErrorCode.BLOB_MISMATCH, str(error)) from error
    if actual != expected:
        raise TextIngestionError(
            IngestionErrorCode.BLOB_MISMATCH,
            "blob store returned a reference that does not match content",
        )


def _find_revision(
    events: tuple[DomainEvent, ...], source_id: SourceId, revision_id: RevisionId
) -> SourceRevisionIngested | None:
    for event in events:
        if (
            event.event_type != SOURCE_REVISION_INGESTED
            or event.schema_version != SOURCE_REVISION_SCHEMA_VERSION
        ):
            continue
        decoded = decode_source_revision_ingested(event.payload)
        if decoded.source.source_id == source_id and decoded.source.revision_id == revision_id:
            return decoded
    return None
