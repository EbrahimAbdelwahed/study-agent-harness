from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from study_agent.adapters.sqlite import (
    LexicalIndexIntegrityError,
    SQLiteLexicalSurfaces,
)
from study_agent.adapters.sqlite.literal_query import compile_medical_trigram_query
from study_agent.domain import (
    DialectProfile,
    RetrievableUnit,
    RevisionId,
    ScopeId,
    SourceId,
    TextSpan,
    UnitKind,
    UnitMeta,
    unit_id_for,
)
from study_agent.domain.identifiers import substrate_id_for
from study_agent.knowledge.lexical import LexicalCorpusItem, LexicalProjector
from study_agent.knowledge.projections import project_structural
from study_agent.knowledge.tree import admit_tree, build_document_tree
from study_agent.ports.knowledge import (
    LexicalProjectionBinding,
    LexicalQuery,
    LexicalSurface,
)


class Catalog:
    def __init__(self, bindings: tuple[LexicalProjectionBinding, ...]) -> None:
        self.values = bindings

    def bindings(self, scope_id: ScopeId) -> tuple[LexicalProjectionBinding, ...]:
        return tuple(item for item in self.values if item.scope_id == scope_id)


def binding(
    text: str,
    *,
    scope: str = "exam-a",
    source: str = "source-a",
    revision: str = "revision-a",
    start: int = 0,
    lexical: bool = False,
) -> LexicalProjectionBinding:
    substrate = substrate_id_for(text.encode("utf-8"))
    profile = DialectProfile("markdown", "v1")
    tree = build_document_tree(text, profile, substrate_id=substrate)
    admitted = admit_tree(tree, text, profile)
    span = TextSpan(substrate, start, len(text))
    revision_id = RevisionId(revision)
    unit = RetrievableUnit(
        unit_id_for(
            revision_id=revision_id,
            structural_path=(),
            unit_kind=UnitKind.PASSAGE.value,
            granularity=3,
            canonical_ref=span.to_json(),
            unitizer_version="unitizer-v1",
        ),
        SourceId(source),
        revision_id,
        UnitKind.PASSAGE,
        3,
        (),
        span,
        UnitMeta("notes", "primary", 80),
    )
    structural = project_structural(unit, admitted)
    projection = (
        LexicalProjector(
            (LexicalCorpusItem(unit, structural, text[start:], admitted),),
            scope_id=scope,
        ).project_all()[0]
        if lexical
        else structural
    )
    return LexicalProjectionBinding(ScopeId(scope), projection, unit, text.encode("utf-8"))


def adapter(tmp_path: Path, values: tuple[LexicalProjectionBinding, ...]) -> SQLiteLexicalSurfaces:
    catalog = Catalog(values)
    result = SQLiteLexicalSurfaces(tmp_path / "kb.sqlite3", catalog)
    result.index(values)
    return result


def test_medical_substrings_and_identifiers_are_literal_and_surface_local(tmp_path: Path) -> None:
    value = binding("prefix sovraspinato fosforilazione IL-6 H2O2", start=7, lexical=True)
    retrieval = adapter(tmp_path, (value,))

    for query in ("spinato", "fosforil", "IL-6", "H2O2"):
        result = retrieval.search(LexicalQuery(ScopeId("exam-a"), query, LexicalSurface.CANONICAL))
        assert [item.unit_id for item in result.candidates] == [value.unit_id]
    terms = retrieval.search(
        LexicalQuery(ScopeId("exam-a"), "il-6", LexicalSurface.TERMS)
    )
    assert [item.unit_id for item in terms.candidates] == [value.unit_id]
    assert compile_medical_trigram_query('OR "NEAR" column:value; DROP TABLE x') == (
        '"or" AND "near" AND "column" AND "value" AND "drop" AND "table" AND "x"'
    )


def test_scope_isolation_and_deterministic_ties(tmp_path: Path) -> None:
    first = binding("shared anatomy", scope="exam-a", source="source-a")
    second = binding("shared anatomy", scope="exam-b", source="source-b")
    retrieval = adapter(tmp_path, (first, second))
    only_a = retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))
    assert [item.unit_id for item in only_a.candidates] == [first.unit_id]

    first_b = binding("shared anatomy", source="source-c", revision="revision-c")
    retrieval = adapter(tmp_path, (first, first_b))
    result = retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))
    assert [item.unit_id for item in result.candidates] == sorted(
        [first.unit_id, first_b.unit_id], key=str
    )
    assert result.candidates[0].rank == 1
    assert result.candidates[1].rank == 2


def test_tampered_and_extra_rows_fail_closed(tmp_path: Path) -> None:
    value = binding("canonical anatomy")
    retrieval = adapter(tmp_path, (value,))
    with sqlite3.connect(tmp_path / "kb.sqlite3") as connection:
        connection.execute(
            "UPDATE lex_canonical SET text = 'tampered' WHERE unit_id = ?",
            (str(value.unit_id),),
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="canonical"):
        retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))


def test_failed_rebuild_preserves_previous_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = binding("first anatomy")
    second = binding("second anatomy", source="source-b", revision="revision-b")
    catalog = Catalog((first,))
    retrieval = SQLiteLexicalSurfaces(tmp_path / "kb.sqlite3", catalog)
    retrieval.index((first,))
    before = retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))
    original = SQLiteLexicalSurfaces._insert_binding

    def fail(connection: sqlite3.Connection, item: LexicalProjectionBinding) -> None:
        if item.unit_id == second.unit_id:
            raise RuntimeError("injected rebuild failure")
        original(connection, item)

    monkeypatch.setattr(SQLiteLexicalSurfaces, "_insert_binding", staticmethod(fail))
    catalog.values = (first, second)
    with pytest.raises(RuntimeError, match="injected rebuild failure"):
        retrieval.rebuild((first, second))
    catalog.values = (first,)
    assert (
        retrieval.search(
            LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL)
        )
        == before
    )


def test_empty_literal_is_insufficient_without_touching_rows(tmp_path: Path) -> None:
    value = binding("canonical anatomy")
    retrieval = adapter(tmp_path, (value,))
    result = retrieval.search(LexicalQuery(ScopeId("exam-a"), "!!!", LexicalSurface.CANONICAL))
    assert result.candidates == ()
