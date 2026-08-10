from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from study_agent.domain import (
    BlobRef,
    CorrelationId,
    CourseId,
    DomainEvent,
    ExecutionContext,
    PrincipalKind,
    SourceId,
    SourceKind,
    substrate_id_for,
)
from study_agent.domain.source import SourceRevision
from study_agent.ingestion import (
    CHUNK_MAX_CHARACTERS,
    CHUNKER_POLICY_VERSION,
    NORMALIZATION_POLICY_VERSION,
    TextIngestionService,
    normalize_utf8,
)
from tests.course_fixtures import ExistingCourseView


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 10, 10, 30, tzinfo=UTC)


class _MemoryBlobStore:
    def __init__(self) -> None:
        self._contents: dict[str, bytes] = {}

    def put(self, content: bytes, ref: BlobRef | None = None) -> BlobRef:
        del ref
        result = BlobRef.from_bytes(content)
        self._contents[str(result.id)] = content
        return result

    def get(self, ref: BlobRef) -> bytes:
        return self._contents[str(ref.id)]


class _MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def read(
        self, course_id: CourseId, after_sequence: int = 0
    ) -> Sequence[DomainEvent]:
        return tuple(
            event
            for event in self.events
            if event.course_id == course_id and event.course_sequence > after_sequence
        )

    def append(
        self,
        course_id: CourseId,
        expected_sequence: int,
        events: Sequence[DomainEvent],
    ) -> int:
        batch = tuple(events)
        self.events.extend(batch)
        return batch[-1].course_sequence if batch else expected_sequence


def test_facade_and_ingestion_mint_one_revision_identity_for_one_manifest() -> None:
    content = b"# Heart\n\nCaf\xc3\xa9 myocardium."
    normalized = normalize_utf8(content)
    source_id = SourceId("source-identity-convergence")
    title = "Cardiology notes"
    trust_level = 90
    source_role = "primary"
    created_at = _FixedClock().now()
    metadata = {
        "chunker_version": CHUNKER_POLICY_VERSION,
        "kind": SourceKind.MARKDOWN.value,
        "max_characters": CHUNK_MAX_CHARACTERS,
        "source_role": source_role,
        "title": title,
        "trust_level": trust_level,
    }
    facade_revision = SourceRevision.create(
        source_id=source_id,
        content=content,
        media_type="text/markdown",
        created_at=created_at,
        normalization_version=NORMALIZATION_POLICY_VERSION,
        substrate_id=substrate_id_for(normalized.content),
        metadata=metadata,
    )
    service = TextIngestionService(
        blobs=_MemoryBlobStore(),
        events=_MemoryEventStore(),
        clock=_FixedClock(),
        courses=ExistingCourseView(),
    )

    ingested = service.ingest(
        filename="cardiology.md",
        content=content,
        source_id=source_id,
        title=title,
        trust_level=trust_level,
        source_role=source_role,
        context=ExecutionContext(
            PrincipalKind.SERVICE,
            "trusted-ingestion",
            CourseId("course-identity"),
            CorrelationId("correlation-identity"),
        ),
    )

    assert ingested.source.revision_id == facade_revision.revision_id
