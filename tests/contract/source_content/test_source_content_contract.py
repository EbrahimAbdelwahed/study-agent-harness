from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from study_agent.domain import (
    BlobId,
    BlobRef,
    ChunkId,
    Citation,
    CorrelationId,
    CourseId,
    DomainEvent,
    ExecutionContext,
    PrincipalKind,
    RevisionId,
    SourceId,
)
from study_agent.ingestion import TextIngestionResult, TextIngestionService
from study_agent.retrieval import (
    CourseSourceContent,
    SourceContentError,
    SourceContentErrorCode,
)
from tests.course_fixtures import ExistingCourseView


class MemoryBlobs:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def put(self, content: bytes) -> BlobRef:
        digest = sha256(content).hexdigest()
        ref = BlobRef(BlobId(f"sha256:{digest}"), digest, len(content))
        self.values[str(ref.id)] = content
        return ref

    def get(self, ref: BlobRef) -> bytes:
        return self.values[str(ref.id)]


class MemoryEvents:
    def __init__(self) -> None:
        self.values: list[DomainEvent] = []

    def append(
        self, course_id: CourseId, expected_sequence: int, events: Sequence[DomainEvent]
    ) -> int:
        assert expected_sequence == len(self.values)
        self.values.extend(events)
        return len(self.values)

    def read(self, course_id: CourseId, after_sequence: int = 0) -> Sequence[DomainEvent]:
        return tuple(
            event
            for event in self.values
            if event.course_id == course_id and event.course_sequence > after_sequence
        )


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 11, 12, tzinfo=UTC)


def make_content() -> tuple[CourseSourceContent, RevisionId, RevisionId]:
    blobs = MemoryBlobs()
    events = MemoryEvents()
    service = TextIngestionService(
        blobs=blobs, events=events, clock=Clock(), courses=ExistingCourseView()
    )
    context = ExecutionContext(
        PrincipalKind.SERVICE,
        "ingestion",
        CourseId("course-1"),
        CorrelationId("correlation-1"),
    )
    def ingest_revision(content: bytes) -> TextIngestionResult:
        return service.ingest(
            filename="heart.md",
            content=content,
            source_id=SourceId("source-1"),
            title="Heart notes",
            trust_level=90,
            source_role="primary",
            context=context,
        )

    first = ingest_revision(b"# Heart\n\nFirst revision.")
    second = ingest_revision(
        "# Heart\n\nMitral valve café.".encode()
    )
    return (
        CourseSourceContent(context.course_id, events, blobs),
        first.source.revision_id,
        second.source.revision_id,
    )


def test_source_content_port_catalog_text_documents_and_resolution_contract() -> None:
    content, first_revision, current_revision = make_content()

    catalog = content.catalog()
    assert [record.source.revision_id for record in catalog] == [
        first_revision,
        current_revision,
    ]
    assert [record.is_current_revision for record in catalog] == [False, True]
    assert content.get_text(current_revision) == "# Heart\n\nMitral valve café."
    assert all(document.is_current_revision for document in content.documents())
    assert len(content.documents(include_superseded=True)) > len(content.documents())

    document = content.documents()[1]
    start = document.chunk.start_offset
    full = Citation(
        document.source_id,
        document.revision_id,
        document.chunk.chunk_id,
        start,
        document.chunk.end_offset,
        "caller locator is not authoritative",
    )
    resolved = content.resolve(full)
    assert resolved.text == document.text
    assert resolved.citation.quoted_snippet == document.text
    assert "Heart notes" in resolved.citation.locator

    sub = Citation(
        document.source_id,
        document.revision_id,
        document.chunk.chunk_id,
        start,
        start + 6,
        "ignored",
    )
    assert content.resolve(sub).text == document.text[:6]


def test_historical_selection_becomes_the_only_current_index_input() -> None:
    blobs = MemoryBlobs()
    events = MemoryEvents()
    service = TextIngestionService(
        blobs=blobs, events=events, clock=Clock(), courses=ExistingCourseView()
    )
    context = ExecutionContext(
        PrincipalKind.SERVICE,
        "ingestion",
        CourseId("course-1"),
        CorrelationId("correlation-1"),
    )

    def ingest_revision(content: bytes) -> TextIngestionResult:
        return service.ingest(
            filename="heart.md",
            content=content,
            source_id=SourceId("source-1"),
            title="Heart notes",
            trust_level=90,
            source_role="primary",
            context=context,
        )

    first = ingest_revision(b"Revision A")
    second = ingest_revision(b"Revision B")
    selected = ingest_revision(b"Revision A")
    content = CourseSourceContent(context.course_id, events, blobs)

    assert selected.source.revision_id == first.source.revision_id
    catalog = content.catalog()
    assert [record.is_current_revision for record in catalog] == [True, False]
    documents = content.documents()
    assert documents
    assert {document.revision_id for document in documents} == {
        first.source.revision_id
    }
    assert second.source.revision_id not in {
        document.revision_id for document in documents
    }


def test_resolution_rejects_missing_ownership_bounds_and_wrong_quote() -> None:
    content, _, revision_id = make_content()
    document = content.documents()[0]
    chunk = document.chunk
    cases = (
        (
            Citation(
                SourceId("wrong-source"),
                revision_id,
                chunk.chunk_id,
                chunk.start_offset,
                chunk.end_offset,
                "x",
            ),
            SourceContentErrorCode.OWNERSHIP_MISMATCH,
        ),
        (
            Citation(
                document.source_id,
                revision_id,
                ChunkId("wrong-chunk"),
                chunk.start_offset,
                chunk.end_offset,
                "x",
            ),
            SourceContentErrorCode.OWNERSHIP_MISMATCH,
        ),
        (
            Citation(
                document.source_id,
                revision_id,
                chunk.chunk_id,
                chunk.start_offset,
                chunk.end_offset + 1,
                "x",
            ),
            SourceContentErrorCode.OUT_OF_BOUNDS,
        ),
        (
            Citation(
                document.source_id,
                revision_id,
                chunk.chunk_id,
                chunk.start_offset,
                chunk.end_offset,
                "x",
                "wrong quote",
            ),
            SourceContentErrorCode.QUOTE_MISMATCH,
        ),
    )
    for citation, code in cases:
        with pytest.raises(SourceContentError) as caught:
            content.resolve(citation)
        assert caught.value.code is code

    with pytest.raises(SourceContentError) as missing:
        content.get_text(RevisionId("missing-revision"))
    assert missing.value.code is SourceContentErrorCode.NOT_FOUND
