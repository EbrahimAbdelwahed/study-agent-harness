from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from study_agent.adapters.sqlite import SQLiteFtsRetrieval
from study_agent.domain import (
    ChunkId,
    Citation,
    CourseId,
    ResolvedCitation,
    RevisionId,
    SourceChunk,
    SourceId,
    SourceKind,
)
from study_agent.ports.retrieval import (
    EvidenceStatus,
    RetrievalDocument,
    RetrievalQuery,
)


class FixtureContent:
    def __init__(self, documents: tuple[RetrievalDocument, ...]) -> None:
        self._documents = {item.chunk.chunk_id: item for item in documents}

    def get_text(self, revision_id: RevisionId) -> str:
        return next(
            item.text for item in self._documents.values() if item.revision_id == revision_id
        )

    def documents(
        self, *, include_superseded: bool = False
    ) -> tuple[RetrievalDocument, ...]:
        return tuple(
            item
            for item in self._documents.values()
            if include_superseded or item.is_current_revision
        )

    def canonical_document(self, chunk_id: ChunkId) -> RetrievalDocument:
        return self._documents[chunk_id]

    def resolve(self, citation: Citation) -> ResolvedCitation:
        item = self._documents[citation.chunk_id]
        resolved = Citation(
            item.source_id,
            item.revision_id,
            item.chunk.chunk_id,
            item.chunk.start_offset,
            item.chunk.end_offset,
            f"fixture:{item.chunk.chunk_id}",
            item.text,
        )
        return ResolvedCitation(resolved, item.text)


def fixture_document(chunk_id: str, source_id: str, text: str) -> RetrievalDocument:
    source = SourceId(source_id)
    revision = RevisionId(f"revision-{source_id}")
    digest = sha256(text.encode()).hexdigest()
    chunk = SourceChunk(
        ChunkId(chunk_id),
        source,
        revision,
        0,
        len(text),
        (),
        0,
        digest,
        "chunker-v1",
    )
    return RetrievalDocument(
        CourseId("course-1"),
        source,
        revision,
        chunk,
        text,
        source_id,
        SourceKind.TEXT,
        "primary",
        90,
        True,
    )


def test_fixed_lexical_expected_sources_and_injection_strings(tmp_path: Path) -> None:
    documents = (
        fixture_document("chunk-heart", "heart", "mitral valve cardiac anatomy"),
        fixture_document("chunk-kidney", "kidney", "glomerular renal filtration"),
    )
    retrieval = SQLiteFtsRetrieval(
        tmp_path / "fixtures.sqlite3", FixtureContent(documents)
    )
    retrieval.index(documents)

    heart = retrieval.search(RetrievalQuery(CourseId("course-1"), "mitral valve"))
    kidney = retrieval.search(
        RetrievalQuery(CourseId("course-1"), "glomerular filtration")
    )
    injection = retrieval.search(
        RetrievalQuery(
            CourseId("course-1"),
            'mitral OR renal"; DROP TABLE retrieval_documents; --',
        )
    )
    still_available = retrieval.search(
        RetrievalQuery(CourseId("course-1"), "mitral valve")
    )

    assert [item.chunk.chunk_id for item in heart.evidence] == [ChunkId("chunk-heart")]
    assert [item.chunk.chunk_id for item in kidney.evidence] == [ChunkId("chunk-kidney")]
    assert injection.status is EvidenceStatus.INSUFFICIENT
    assert still_available == heart
