from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from study_agent.adapters.filesystem import FilesystemBlobStore
from study_agent.adapters.sqlite import SQLiteEventStore, SQLiteLexicalSurfaces
from study_agent.domain import (
    CorrelationId,
    CourseId,
    EvidencePacketStatus,
    ExecutionContext,
    PrincipalKind,
    ScopeId,
    SourceId,
    UnitMeta,
)
from study_agent.domain.identifiers import substrate_id_for
from study_agent.domain.tree import DialectProfile, HeadingSyntax
from study_agent.ingestion import TextIngestionService, register_source_revision_events
from study_agent.knowledge.lexical import LexicalCorpusItem, LexicalProjector
from study_agent.knowledge.projections import project_structural
from study_agent.knowledge.tree import admit_tree, build_document_tree
from study_agent.knowledge.unitizer import unitize
from study_agent.knowledge.units import RevisionBinding
from study_agent.ports.knowledge import LexicalProjectionBinding, LexicalSurface
from study_agent.ports.retrievers import RetrieverHostAuthority
from study_agent.retrieval import EvidenceCatalog, EvidenceService, FusionPolicy, LexicalRetriever
from study_agent.retrieval.registry import RetrieverRegistry
from study_agent.state import EventRegistry


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 1, 10, 30, tzinfo=UTC)


class CourseView:
    def get(self, course_id: CourseId) -> object:
        del course_id
        return object()


class BindingCatalog:
    def __init__(self, bindings: tuple[LexicalProjectionBinding, ...]) -> None:
        self._bindings = bindings

    def bindings(self, scope_id: ScopeId) -> tuple[LexicalProjectionBinding, ...]:
        return tuple(item for item in self._bindings if item.scope_id == scope_id)


def test_real_file_reaches_verified_agent_evidence(tmp_path: Path) -> None:
    """file -> immutable source -> substrate -> tree -> units -> FTS -> verified evidence"""
    source_file = tmp_path / "pericardio.md"
    source_file.write_text(
        "# Pericardio fibroso\n\nIl pericardio fibroso limita la distensione cardiaca.\n",
        encoding="utf-8",
    )
    blobs = FilesystemBlobStore(tmp_path / "blobs")
    registry = EventRegistry()
    register_source_revision_events(registry, blobs.get)
    events = SQLiteEventStore(tmp_path / "events.sqlite3", registry)
    context = ExecutionContext(
        PrincipalKind.SERVICE,
        "trusted-ingestion",
        CourseId("anatomia"),
        CorrelationId("kb13-e2e"),
    )
    ingested = TextIngestionService(
        blobs=blobs,
        events=events,
        clock=FixedClock(),
        courses=CourseView(),  # type: ignore[arg-type]
    ).ingest(
        filename=source_file.name,
        content=source_file.read_bytes(),
        source_id=SourceId("pericardio"),
        title="Pericardio",
        trust_level=90,
        source_role="primary",
        context=context,
    )
    substrate_bytes = blobs.get(ingested.source.normalized_blob)
    substrate_text = substrate_bytes.decode("utf-8")
    substrate_id = substrate_id_for(substrate_bytes)
    profile = DialectProfile("markdown", "v1", heading_syntax=HeadingSyntax.ATX)
    admitted_tree = admit_tree(
        build_document_tree(substrate_text, profile, substrate_id=substrate_id),
        substrate_text,
        profile,
    )
    units = unitize(
        substrate_text,
        admitted_tree.tree,
        revision_id=ingested.source.revision_id,
        binding=RevisionBinding(ingested.source.source_id, substrate_id, len(substrate_text)),
        meta=UnitMeta("notes", "primary", 90),
    )
    structural = tuple(project_structural(unit, admitted_tree) for unit in units)
    lexical = LexicalProjector(
        tuple(
            LexicalCorpusItem(
                unit,
                projection,
                substrate_text[unit.canonical_ref.start : unit.canonical_ref.end],  # type: ignore[union-attr]
                admitted_tree,
            )
            for unit, projection in zip(units, structural, strict=True)
        ),
        scope_id="anatomia-esame",
    ).project_all()
    scope_id = ScopeId("anatomia-esame")
    lexical_by_unit = {projection.unit_id: projection for projection in lexical}
    bindings = tuple(
        LexicalProjectionBinding(scope_id, lexical_by_unit[unit.unit_id], unit, substrate_bytes)
        for unit in units
    )
    index = SQLiteLexicalSurfaces(tmp_path / "kb.sqlite3", BindingCatalog(bindings))
    index.index(bindings)
    retriever = LexicalRetriever(index, LexicalSurface.PROJECTION)
    evidence = EvidenceService(
        registry=RetrieverRegistry((retriever,), RetrieverHostAuthority()),
        catalog=EvidenceCatalog(bindings),
    )

    packet = evidence.search(
        scope_id=scope_id,
        query="pericardio",
        policy=FusionPolicy(retriever_weights=((retriever.manifest.identity, 1.0),)),
    )

    assert packet.status is EvidencePacketStatus.READY
    assert packet.rows
    row = packet.rows[0]
    assert "pericardio" in row.canonical_text.casefold()
    assert row.citation.quoted_sha256
    assert row.retriever_provenance == (retriever.manifest.identity,)
    assert events.verify_projection(context.course_id)
    blobs.close()
