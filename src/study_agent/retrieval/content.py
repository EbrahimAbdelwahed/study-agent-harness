"""Event- and blob-backed canonical source content resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import final

from study_agent.domain.citation_v2 import CitationFailure, CitationFailureKind, TextCitationV2
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.events import DomainEvent
from study_agent.domain.identifiers import (
    ChunkId,
    CourseId,
    EventId,
    RevisionId,
    SourceId,
    substrate_id_for,
)
from study_agent.domain.lineage import SelectionStatus
from study_agent.domain.source import (
    BlobRef,
    Citation,
    ResolvedCitation,
    SourceChunk,
    SourceDocument,
)
from study_agent.domain.units import RetrievableUnit, TextSpan, UnitMeta
from study_agent.ingestion import (
    SOURCE_REVISION_INGESTED,
    SOURCE_REVISION_SCHEMA_VERSION,
    SOURCE_REVISION_SELECTED,
    SOURCE_REVISION_SELECTED_SCHEMA_VERSION,
    SourceRevisionIngested,
    decode_source_revision_event,
    decode_source_revision_selected_event,
)
from study_agent.ingestion.events import MAX_VERIFIED_BLOB_BYTES
from study_agent.knowledge.citation import text_citation_for, verify_text_citation
from study_agent.knowledge.units import admit, unit_from_legacy_chunk
from study_agent.ports.retrieval import RetrievalDocument
from study_agent.ports.storage import (
    BlobStore,
    _envelope_to_legacy,
    _LegacyEventStore,
    _read_bounded_records,
)

from .errors import SourceContentError, SourceContentErrorCode

_MAX_HISTORY_EVENTS = 4_096
_MAX_HISTORY_EVENT_BYTES = 32 * 1024 * 1024
LEGACY_CHUNK_UNITIZER_VERSION = "unitizer-v1"


@dataclass(slots=True)
class _CapturingBlobLoader:
    loader: Callable[[BlobRef], bytes]
    calls: int = 0
    normalized_ref: BlobRef | None = field(default=None, init=False)
    normalized_bytes: bytes | None = field(default=None, init=False, repr=False)

    def __call__(self, ref: BlobRef) -> bytes:
        if type(ref) is not BlobRef or ref.byte_length > MAX_VERIFIED_BLOB_BYTES:
            raise ValueError("verified blob exceeds the bounded content budget")
        self.calls += 1
        value = self.loader(ref)
        # The source decoder loads the original blob first and the normalized
        # blob second.  Do not retain the first value; only the second value,
        # after the decoder has verified it, may be used for minting.
        if self.calls == 2 and type(value) is bytes:
            self.normalized_ref = ref
            self.normalized_bytes = value
        return value

    def normalized(self, ref: BlobRef) -> bytes:
        if self.calls != 2 or type(ref) is not BlobRef:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "normalized blob identity is invalid"
            )
        if self.normalized_ref != ref:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "normalized blob identity is invalid"
            )
        value = self.normalized_bytes
        if type(value) is not bytes:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "normalized blob was not captured from verified content",
            )
        return value


@dataclass(frozen=True, slots=True)
class _VerifiedLegacyCitation:
    _issuer: object = field(repr=False, compare=False)
    course_id: CourseId
    high_water_sequence: int
    source_event_id: EventId
    source: SourceDocument
    chunk: SourceChunk
    substrate_bytes: bytes = field(repr=False, compare=False)
    unit: RetrievableUnit


@dataclass(frozen=True, slots=True)
class SourceRevisionRecord:
    course_id: CourseId
    source: SourceDocument
    chunks: tuple[SourceChunk, ...]
    text: str
    is_current_revision: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "chunks", tuple(self.chunks))


@final
class CourseSourceContent:
    """Read-only canonical source adapter scoped to one course event stream."""

    def __init__(self, course_id: CourseId, events: _LegacyEventStore, blobs: BlobStore) -> None:
        if type(course_id) is not CourseId:
            raise TypeError("course_id must be an exact CourseId")
        self._course_id = course_id
        self._events = events
        self._blobs = blobs
        self._legacy_receipt_issuer = object()

    def _read_events(self) -> tuple[DomainEvent, ...]:
        try:
            bounded = _read_bounded_records(
                self._events,
                self._course_id,
                max_events=_MAX_HISTORY_EVENTS,
                max_encoded_bytes=_MAX_HISTORY_EVENT_BYTES,
            )
            events = tuple(
                event
                if isinstance(event, DomainEvent)
                else _envelope_to_legacy(event)
                for event in bounded.records
            )
            previous_sequence = 0
            for event in events:
                if type(event) is not DomainEvent or type(event.course_sequence) is not int:
                    raise CitationFailure(
                        CitationFailureKind.CORRUPT,
                        "course history envelope is not canonical",
                    )
                if event.course_sequence <= previous_sequence:
                    raise CitationFailure(
                        CitationFailureKind.CORRUPT,
                        "course history is not ordered",
                    )
                previous_sequence = event.course_sequence
                if (
                    type(event.course_id) is not CourseId
                    or event.course_id.value != self._course_id.value
                ):
                    raise CitationFailure(
                        CitationFailureKind.CORRUPT,
                        "course history belongs to another course",
                    )
            return events
        except CitationFailure:
            raise
        except ValidationFailure as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "course history could not be verified",
            ) from error
        except (LookupError, OSError, TypeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT,
                "course history could not be verified",
            ) from error

    def _decode(
        self,
    ) -> tuple[
        tuple[tuple[SourceRevisionIngested, str], ...],
        dict[SourceId, RevisionId],
    ]:
        decoded: list[tuple[SourceRevisionIngested, str]] = []
        seen: dict[tuple[SourceId, RevisionId], SourceRevisionIngested] = {}
        current: dict[SourceId, RevisionId] = {}
        for event in self._read_events():
            if event.course_sequence < 1:
                raise SourceContentError(
                    SourceContentErrorCode.INTEGRITY_ERROR,
                    "source history sequence is invalid",
                )
            if (
                event.event_type == SOURCE_REVISION_SELECTED
            ):
                if event.schema_version != SOURCE_REVISION_SELECTED_SCHEMA_VERSION:
                    raise SourceContentError(
                        SourceContentErrorCode.INTEGRITY_ERROR,
                        "source selection schema is unsupported",
                    )
                try:
                    selection = decode_source_revision_selected_event(event)
                    if (selection.source_id, selection.revision_id) not in seen:
                        raise ValueError("selected revision does not exist in source history")
                except ValueError as error:
                    raise SourceContentError(
                        SourceContentErrorCode.INTEGRITY_ERROR,
                        "source selection event failed integrity validation",
                    ) from error
                current[selection.source_id] = selection.revision_id
                continue
            if event.event_type != SOURCE_REVISION_INGESTED:
                continue
            try:
                captured = _CapturingBlobLoader(self._blobs.get)
                revision = decode_source_revision_event(event, captured)
                normalized = captured.normalized(revision.source.normalized_blob)
                text = normalized.decode("utf-8", errors="strict")
            except LookupError as error:
                raise SourceContentError(
                    SourceContentErrorCode.NOT_FOUND,
                    "source content blob is missing",
                ) from error
            except (OSError, UnicodeError, ValueError) as error:
                raise SourceContentError(
                    SourceContentErrorCode.INTEGRITY_ERROR,
                    "source event or content failed integrity validation",
                ) from error
            key = (revision.source.source_id, revision.source.revision_id)
            existing = seen.get(key)
            if existing is not None:
                raise SourceContentError(
                    SourceContentErrorCode.INTEGRITY_ERROR,
                    "revision identity has duplicate immutable manifests",
                )
            seen[key] = revision
            decoded.append((revision, text))
            current[revision.source.source_id] = revision.source.revision_id
        return tuple(decoded), current

    def upgrade_legacy_citation(self, citation: Citation) -> TextCitationV2:
        receipt = self._verify_legacy_citation(citation)
        return self._mint_verified_legacy_citation(receipt, citation)

    def _verify_legacy_citation(self, citation: Citation) -> _VerifiedLegacyCitation:
        if type(citation) is not Citation:
            raise CitationFailure(
                CitationFailureKind.UNSUPPORTED_VERSION,
                "legacy citation expected",
            )
        if any(
            type(value) is not expected
            for value, expected in (
                (citation.source_id, SourceId),
                (citation.revision_id, RevisionId),
                (citation.chunk_id, ChunkId),
            )
        ):
            raise CitationFailure(
                CitationFailureKind.REFERENCE_MISMATCH,
                "legacy citation identifiers are not canonical",
            )
        if type(citation.start_offset) is not int or type(citation.end_offset) is not int:
            raise CitationFailure(
                CitationFailureKind.MALFORMED_SPAN, "legacy citation span is invalid"
            )
        if citation.start_offset < 0 or citation.end_offset <= citation.start_offset:
            raise CitationFailure(
                CitationFailureKind.MALFORMED_SPAN, "legacy citation span is invalid"
            )
        if type(citation.locator) is not str or (
            citation.quoted_snippet is not None and type(citation.quoted_snippet) is not str
        ):
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "legacy citation fields are not canonical"
            )

        events = self._read_events()
        matches: list[DomainEvent] = []
        for event in events:
            if event.event_type != SOURCE_REVISION_INGESTED:
                continue
            if event.schema_version not in (1, SOURCE_REVISION_SCHEMA_VERSION):
                raise CitationFailure(
                    CitationFailureKind.UNSUPPORTED_VERSION,
                    "source revision event schema is unsupported",
                )
            source_payload = event.payload.get("source")
            if not isinstance(source_payload, Mapping):
                raise CitationFailure(
                    CitationFailureKind.CORRUPT, "source event manifest is invalid"
                )
            source_id = source_payload.get("source_id")
            revision_id = source_payload.get("revision_id")
            if type(source_id) is not str or type(revision_id) is not str:
                raise CitationFailure(
                    CitationFailureKind.CORRUPT, "source event identity is invalid"
                )
            if source_id == citation.source_id.value and revision_id == citation.revision_id.value:
                matches.append(event)
        if not matches:
            raise CitationFailure(
                CitationFailureKind.MISSING, "legacy citation source binding is missing"
            )
        if len(matches) != 1:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "legacy citation source binding is ambiguous"
            )

        event = matches[0]
        if type(event.event_id) is not EventId:
            raise CitationFailure(CitationFailureKind.CORRUPT, "source event identity is invalid")
        captured = _CapturingBlobLoader(self._blobs.get)
        revision: SourceRevisionIngested
        try:
            revision = decode_source_revision_event(event, captured)
        except CitationFailure:
            raise
        except KeyError as error:
            raise CitationFailure(
                CitationFailureKind.MISSING, "canonical source blob is missing"
            ) from error
        except (LookupError, OSError, TypeError, UnicodeError, ValueError) as error:
            kind = (
                CitationFailureKind.MISSING
                if isinstance(error.__cause__, KeyError)
                else CitationFailureKind.CORRUPT
            )
            raise CitationFailure(kind, "canonical source proof failed") from error

        source = revision.source
        if (
            type(source) is not SourceDocument
            or type(source.source_id) is not SourceId
            or type(source.revision_id) is not RevisionId
        ):
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "decoded source identity is not canonical"
            )
        if (
            source.source_id.value != citation.source_id.value
            or source.revision_id.value != citation.revision_id.value
        ):
            raise CitationFailure(
                CitationFailureKind.REFERENCE_MISMATCH,
                "source revision does not match the citation",
            )
        chunks = tuple(
            chunk
            for chunk in revision.chunks
            if type(chunk) is SourceChunk
            and type(chunk.chunk_id) is ChunkId
            and chunk.source_id.value == citation.source_id.value
            and chunk.revision_id.value == citation.revision_id.value
            and chunk.chunk_id.value == citation.chunk_id.value
        )
        if len(chunks) == 0:
            raise CitationFailure(CitationFailureKind.MISSING, "legacy citation chunk is missing")
        if len(chunks) != 1:
            raise CitationFailure(CitationFailureKind.CORRUPT, "legacy citation chunk is ambiguous")
        chunk = chunks[0]
        normalized = captured.normalized(source.normalized_blob)
        if type(normalized) is not bytes or not normalized:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "canonical substrate bytes are invalid"
            )
        try:
            derived_substrate = substrate_id_for(normalized)
        except (TypeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "canonical substrate identity is invalid"
            ) from error
        expected_substrate = f"substrate:sha256:{source.normalized_blob.checksum_sha256}"
        if (
            derived_substrate.value != expected_substrate
            or derived_substrate.value != source.substrate_id.value
        ):
            raise CitationFailure(
                CitationFailureKind.REFERENCE_MISMATCH,
                "canonical substrate does not match the citation",
            )
        try:
            text = normalized.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "canonical substrate is not UTF-8"
            ) from error
        meta = UnitMeta(
            source_class=source.kind.value,
            role=source.source_role,
            trust_level=source.trust_level,
            ordinal=chunk.ordinal,
        )
        try:
            unit = unit_from_legacy_chunk(
                chunk,
                substrate_id=derived_substrate,
                meta=meta,
            )
            admit(unit, unitizer_version=LEGACY_CHUNK_UNITIZER_VERSION)
        except (TypeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "legacy unit derivation failed"
            ) from error
        span = unit.canonical_ref
        if type(span) is not TextSpan:
            raise CitationFailure(
                CitationFailureKind.REFERENCE_MISMATCH, "legacy unit is not a text span"
            )
        if (
            citation.start_offset < chunk.start_offset
            or citation.end_offset > chunk.end_offset
            or citation.start_offset < span.start
            or citation.end_offset > span.end
            or citation.end_offset > len(text)
        ):
            raise CitationFailure(
                CitationFailureKind.OUT_OF_UNIT, "legacy citation span escapes its unit"
            )
        quoted = text[citation.start_offset : citation.end_offset]
        try:
            quoted.encode("utf-8", errors="strict")
            if citation.quoted_snippet is not None:
                citation.quoted_snippet.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "legacy citation text is not UTF-8"
            ) from error
        if citation.quoted_snippet is not None and citation.quoted_snippet != quoted:
            raise CitationFailure(
                CitationFailureKind.MISMATCHED_CHECKSUM, "legacy citation snippet does not match"
            )
        return _VerifiedLegacyCitation(
            self._legacy_receipt_issuer,
            self._course_id,
            events[-1].course_sequence,
            event.event_id,
            source,
            chunk,
            normalized,
            unit,
        )

    def _mint_verified_legacy_citation(
        self, receipt: _VerifiedLegacyCitation, citation: Citation
    ) -> TextCitationV2:
        if receipt._issuer is not self._legacy_receipt_issuer:
            raise CitationFailure(CitationFailureKind.CORRUPT, "invalid legacy receipt")
        if receipt.course_id.value != self._course_id.value:
            raise CitationFailure(
                CitationFailureKind.REFERENCE_MISMATCH, "legacy receipt belongs to another course"
            )
        try:
            upgraded = text_citation_for(
                receipt.unit,
                substrate_bytes=receipt.substrate_bytes,
                start=citation.start_offset,
                end=citation.end_offset,
                locator=citation.locator,
            )
            verify_text_citation(
                upgraded,
                substrate_bytes=receipt.substrate_bytes,
                unit=receipt.unit,
                selection_status=SelectionStatus.CURRENT,
            )
            return upgraded
        except CitationFailure:
            raise
        except (TypeError, ValueError) as error:
            raise CitationFailure(
                CitationFailureKind.CORRUPT, "legacy citation minting failed"
            ) from error

    def catalog(self) -> tuple[SourceRevisionRecord, ...]:
        decoded, current = self._decode()
        return tuple(
            SourceRevisionRecord(
                self._course_id,
                revision.source,
                revision.chunks,
                text,
                current[revision.source.source_id] == revision.source.revision_id,
            )
            for revision, text in decoded
        )

    def documents(self, *, include_superseded: bool = False) -> tuple[RetrievalDocument, ...]:
        documents: list[RetrievalDocument] = []
        for record in self.catalog():
            if not include_superseded and not record.is_current_revision:
                continue
            for chunk in record.chunks:
                documents.append(
                    RetrievalDocument(
                        self._course_id,
                        record.source.source_id,
                        record.source.revision_id,
                        chunk,
                        record.text[chunk.start_offset : chunk.end_offset],
                        record.source.title,
                        record.source.kind,
                        record.source.source_role,
                        record.source.trust_level,
                        record.is_current_revision,
                    )
                )
        return tuple(documents)

    def _record(self, revision_id: RevisionId) -> SourceRevisionRecord:
        for record in self.catalog():
            if record.source.revision_id == revision_id:
                return record
        raise SourceContentError(
            SourceContentErrorCode.NOT_FOUND,
            f"source revision {revision_id} was not found in course {self._course_id}",
        )

    def get_text(self, revision_id: RevisionId) -> str:
        return self._record(revision_id).text

    def canonical_document(self, chunk_id: ChunkId) -> RetrievalDocument:
        for document in self.documents(include_superseded=True):
            if document.chunk.chunk_id == chunk_id:
                return document
        raise SourceContentError(
            SourceContentErrorCode.NOT_FOUND,
            f"source chunk {chunk_id} was not found in course {self._course_id}",
        )

    @staticmethod
    def _locator(record: SourceRevisionRecord, chunk: SourceChunk, start: int, end: int) -> str:
        section = " > ".join(chunk.section_path) or f"chunk {chunk.ordinal + 1}"
        return f"{record.source.title} · {section} · chars {start}-{end}"

    def resolve(self, citation: Citation) -> ResolvedCitation:
        record = self._record(citation.revision_id)
        if record.source.source_id != citation.source_id:
            raise SourceContentError(
                SourceContentErrorCode.OWNERSHIP_MISMATCH,
                "citation source does not own the declared revision",
            )
        chunk = next(
            (item for item in record.chunks if item.chunk_id == citation.chunk_id),
            None,
        )
        if chunk is None:
            raise SourceContentError(
                SourceContentErrorCode.OWNERSHIP_MISMATCH,
                "citation chunk does not belong to the declared revision",
            )
        if citation.start_offset < chunk.start_offset or citation.end_offset > chunk.end_offset:
            raise SourceContentError(
                SourceContentErrorCode.OUT_OF_BOUNDS,
                "citation span must lie entirely inside its declared chunk",
            )
        text = record.text[citation.start_offset : citation.end_offset]
        if citation.quoted_snippet is not None and citation.quoted_snippet != text:
            raise SourceContentError(
                SourceContentErrorCode.QUOTE_MISMATCH,
                "citation quote does not match canonical normalized text",
            )
        canonical = Citation(
            citation.source_id,
            citation.revision_id,
            citation.chunk_id,
            citation.start_offset,
            citation.end_offset,
            self._locator(record, chunk, citation.start_offset, citation.end_offset),
            text,
        )
        return ResolvedCitation(canonical, text)
