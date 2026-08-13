from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import pytest

from study_agent.domain import ChunkId, Citation, CourseId, DomainEvent, RevisionId, SourceId
from study_agent.domain._validation import JsonValue
from study_agent.domain.citation_v2 import CitationFailure, CitationFailureKind
from study_agent.domain.errors import ValidationFailure
from study_agent.domain.source import BlobRef
from study_agent.ports.storage import BlobStore, _BoundedEventRead, _LegacyEventStore
from study_agent.retrieval import CourseSourceContent
from tests.unit.ingestion.test_source_revision_state import make_event


@dataclass
class _Events:
    event: DomainEvent

    def read(self, course_id: CourseId, after_sequence: int = 0) -> tuple[DomainEvent, ...]:
        assert course_id == CourseId("course-1")
        assert after_sequence == 0
        return (self.event,)

    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int:
        raise AssertionError("source owner must not append events")

    def _read_records_bounded(
        self,
        course_id: CourseId,
        *,
        max_events: int,
        max_encoded_bytes: int,
        after_sequence: int = 0,
    ) -> _BoundedEventRead:
        assert course_id == CourseId("course-1")
        assert max_events == 4_096
        assert max_encoded_bytes == 32 * 1024 * 1024
        assert after_sequence == 0
        return _BoundedEventRead((self.event,), self.event.course_sequence)


@dataclass
class _UnboundedOnlyEvents:
    event: DomainEvent

    def read(self, course_id: CourseId, after_sequence: int = 0) -> tuple[DomainEvent, ...]:
        raise AssertionError("CourseSourceContent must not fall back to unbounded reads")

    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int:
        raise AssertionError("source owner must not append events")


@dataclass
class _CorruptBoundedEvents(_Events):
    def _read_records_bounded(
        self,
        course_id: CourseId,
        *,
        max_events: int,
        max_encoded_bytes: int,
        after_sequence: int = 0,
    ) -> _BoundedEventRead:
        raise ValidationFailure("Bearer secret=/private/history")


class _Blobs:
    def __init__(self, loader: Callable[[BlobRef], bytes]) -> None:
        self._loader = loader

    def get(self, ref: BlobRef) -> bytes:
        return self._loader(ref)

    def put(self, content: bytes, ref: BlobRef | None = None) -> BlobRef:
        raise AssertionError("source owner must not write blobs")


def test_course_owner_upgrades_current_source_from_its_event_and_blob_store() -> None:
    event, loader = make_event()
    raw_source = event.payload["source"]
    assert isinstance(raw_source, Mapping)
    source = raw_source
    raw_chunks = event.payload["chunks"]
    assert isinstance(raw_chunks, tuple)
    raw_chunk = raw_chunks[0]
    assert isinstance(raw_chunk, Mapping)
    chunk = raw_chunk
    source_id = SourceId(cast(str, source["source_id"]))
    revision_id = RevisionId(cast(str, source["revision_id"]))
    citation = Citation(
        source_id=source_id,
        revision_id=revision_id,
        chunk_id=ChunkId(cast(str, chunk["chunk_id"])),
        start_offset=cast(int, chunk["start_offset"]),
        end_offset=cast(int, chunk["end_offset"]),
        locator="untrusted locator",
    )

    upgraded = CourseSourceContent(
        CourseId("course-1"),
        cast(_LegacyEventStore, _Events(event)),
        cast(BlobStore, _Blobs(loader)),
    ).upgrade_legacy_citation(citation)

    assert upgraded.source_id == source_id
    assert upgraded.revision_id == citation.revision_id
    assert upgraded.start == citation.start_offset
    assert upgraded.end == citation.end_offset


def test_course_owner_replays_schema_one_without_a_legacy_snippet() -> None:
    event, loader = make_event(legacy_identity=True)
    raw_source = event.payload["source"]
    raw_chunks = event.payload["chunks"]
    assert isinstance(raw_source, Mapping)
    assert isinstance(raw_chunks, tuple)
    source = raw_source
    chunk = cast(Mapping[str, JsonValue], raw_chunks[0])
    citation = Citation(
        SourceId(cast(str, source["source_id"])),
        RevisionId(cast(str, source["revision_id"])),
        ChunkId(cast(str, chunk["chunk_id"])),
        cast(int, chunk["start_offset"]),
        cast(int, chunk["end_offset"]),
        "legacy locator",
    )

    upgraded = CourseSourceContent(
        CourseId("course-1"),
        cast(_LegacyEventStore, _Events(event)),
        cast(BlobStore, _Blobs(loader)),
    ).upgrade_legacy_citation(citation)

    assert upgraded.source_id == citation.source_id
    assert upgraded.revision_id == citation.revision_id
    assert upgraded.start == citation.start_offset
    assert upgraded.end == citation.end_offset


def test_course_owner_rejects_citation_subclasses_before_reading_history() -> None:
    event, loader = make_event()

    class CitationSubclass(Citation):
        pass

    citation = CitationSubclass(
        SourceId("source-1"),
        RevisionId(
            cast(str, cast(Mapping[str, JsonValue], event.payload["source"])["revision_id"])
        ),
        ChunkId(
            cast(
                str,
                cast(Mapping[str, JsonValue], cast(tuple[object, ...], event.payload["chunks"])[0])[
                    "chunk_id"
                ],
            )
        ),
        0,
        1,
        "locator",
    )
    owner = CourseSourceContent(
        CourseId("course-1"),
        cast(_LegacyEventStore, _Events(event)),
        cast(BlobStore, _Blobs(loader)),
    )
    with pytest.raises(CitationFailure) as error:
        owner.upgrade_legacy_citation(citation)
    assert error.value.kind is CitationFailureKind.UNSUPPORTED_VERSION


def test_course_owner_fails_closed_without_the_bounded_storage_seam() -> None:
    event, loader = make_event()
    source = cast(Mapping[str, JsonValue], event.payload["source"])
    chunks = cast(tuple[JsonValue, ...], event.payload["chunks"])
    chunk = cast(Mapping[str, JsonValue], chunks[0])
    citation = Citation(
        SourceId(cast(str, source["source_id"])),
        RevisionId(cast(str, source["revision_id"])),
        ChunkId(cast(str, chunk["chunk_id"])),
        cast(int, chunk["start_offset"]),
        cast(int, chunk["end_offset"]),
        "locator",
    )
    owner = CourseSourceContent(
        CourseId("course-1"),
        cast(_LegacyEventStore, _UnboundedOnlyEvents(event)),
        cast(BlobStore, _Blobs(loader)),
    )
    with pytest.raises(CitationFailure) as error:
        owner.upgrade_legacy_citation(citation)
    assert error.value.kind is CitationFailureKind.CORRUPT


def test_course_owner_redacts_bounded_storage_validation_failure() -> None:
    event, loader = make_event()
    source = cast(Mapping[str, JsonValue], event.payload["source"])
    chunks = cast(tuple[JsonValue, ...], event.payload["chunks"])
    chunk = cast(Mapping[str, JsonValue], chunks[0])
    citation = Citation(
        SourceId(cast(str, source["source_id"])),
        RevisionId(cast(str, source["revision_id"])),
        ChunkId(cast(str, chunk["chunk_id"])),
        cast(int, chunk["start_offset"]),
        cast(int, chunk["end_offset"]),
        "locator",
    )
    owner = CourseSourceContent(
        CourseId("course-1"),
        cast(_LegacyEventStore, _CorruptBoundedEvents(event)),
        cast(BlobStore, _Blobs(loader)),
    )
    with pytest.raises(CitationFailure) as error:
        owner.upgrade_legacy_citation(citation)
    assert error.value.kind is CitationFailureKind.CORRUPT
    assert "Bearer" not in str(error.value)
    assert "/private/history" not in str(error.value)
