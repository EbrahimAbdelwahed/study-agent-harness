from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from study_agent.adapters.sqlite import (
    LexicalIndexIntegrityError,
    SQLiteFtsRetrieval,
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


class FlippingCatalog(Catalog):
    def __init__(
        self,
        initial: tuple[LexicalProjectionBinding, ...],
        replacement: tuple[LexicalProjectionBinding, ...],
    ) -> None:
        super().__init__(initial)
        self._replacement = replacement
        self.calls = 0

    def bindings(self, scope_id: ScopeId) -> tuple[LexicalProjectionBinding, ...]:
        self.calls += 1
        values = self.values if self.calls <= 2 else self._replacement
        return tuple(item for item in values if item.scope_id == scope_id)


class EmptyRetrievalCatalog:
    def documents(self, *, include_superseded: bool = False) -> tuple[object, ...]:
        del include_superseded
        return ()


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
    with pytest.raises(ValueError, match="query_fingerprint"):
        replace(terms.candidates[0], query_fingerprint="")
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


def test_scope_rank_is_invariant_to_other_scope_corpus(tmp_path: Path) -> None:
    first = binding("shared anatomy anatomy", source="source-a", revision="revision-a")
    second = binding("shared anatomy", source="source-b", revision="revision-b")
    (tmp_path / "baseline").mkdir()
    baseline = adapter(tmp_path / "baseline", (first, second))
    baseline_result = baseline.search(
        LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL)
    )

    other = binding(
        "anatomy anatomy anatomy anatomy anatomy",
        scope="exam-b",
        source="source-c",
        revision="revision-c",
    )
    (tmp_path / "expanded").mkdir()
    expanded = adapter(tmp_path / "expanded", (first, second, other))
    expanded_result = expanded.search(
        LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL)
    )
    assert expanded_result == baseline_result


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


def test_scope_receipt_generation_and_fingerprint_are_bound(tmp_path: Path) -> None:
    value = binding("canonical anatomy")
    retrieval = adapter(tmp_path, (value,))
    database = tmp_path / "kb.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE kb_lex_receipts SET generation = generation + 1 WHERE scope_id = ?",
            ("exam-a",),
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="stale or forged"):
        retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))

    (tmp_path / "fingerprint").mkdir()
    retrieval = adapter(tmp_path / "fingerprint", (value,))
    with sqlite3.connect(tmp_path / "fingerprint" / "kb.sqlite3") as connection:
        connection.execute(
            "UPDATE kb_lex_receipts SET catalog_fingerprint = ? WHERE scope_id = ?",
            ("f" * 64, "exam-a"),
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="stale or forged"):
        retrieval.search(
            LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL)
        )


def test_unknown_and_unbound_reserved_schema_fail_closed(tmp_path: Path) -> None:
    value = binding("canonical anatomy")
    database = tmp_path / "unknown.sqlite3"
    (tmp_path / "ready").mkdir()
    retrieval = adapter(tmp_path / "ready", (value,))
    del retrieval
    with sqlite3.connect(tmp_path / "ready" / "kb.sqlite3") as connection:
        connection.execute("CREATE TABLE kb_lex_unexpected_state(value TEXT)")
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="unknown or missing"):
        SQLiteLexicalSurfaces(tmp_path / "ready" / "kb.sqlite3", Catalog((value,)))

    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE kb_lex_bindings(scope_id TEXT)")
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="reserved lexical"):
        SQLiteLexicalSurfaces(database, Catalog((value,)))


def test_schema_initialization_rolls_back_every_ddl_on_fault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "rollback.sqlite3"
    original = SQLiteLexicalSurfaces._create_surface

    def fail_on_terms(connection: sqlite3.Connection, table: str) -> None:
        if table == "lex_terms":
            raise RuntimeError("injected schema fault")
        original(connection, table)

    monkeypatch.setattr(SQLiteLexicalSurfaces, "_create_surface", staticmethod(fail_on_terms))
    with pytest.raises(RuntimeError, match="injected schema fault"):
        SQLiteLexicalSurfaces(database, Catalog(()))
    with sqlite3.connect(database) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == []


def test_schema_rejects_wrong_tokenizer_and_newer_row_but_coexists_with_v01(
    tmp_path: Path,
) -> None:
    value = binding("canonical anatomy")
    retrieval = adapter(tmp_path, (value,))
    database = tmp_path / "kb.sqlite3"
    SQLiteFtsRetrieval(database, EmptyRetrievalCatalog())
    assert [item.unit_id for item in retrieval.search(
        LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL)
    ).candidates] == [value.unit_id]

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = replace(sql, 'trigram', 'unicode61') "
            "WHERE name = 'lex_projection'"
        )
        connection.execute("PRAGMA writable_schema = OFF")
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="FTS configuration"):
        SQLiteLexicalSurfaces(database, Catalog((value,)), read_only=True).audit(
            ScopeId("exam-a"), bindings=(value,)
        )

    (tmp_path / "newer").mkdir()
    retrieval = adapter(tmp_path / "newer", (value,))
    newer = tmp_path / "newer" / "kb.sqlite3"
    with sqlite3.connect(newer) as connection:
        connection.execute(
            "UPDATE kb_lex_schema SET schema_version = ? WHERE schema_name = ?",
            ("sqlite-lexical-schema-v2", "sqlite-lexical-schema-v1"),
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="schema receipt"):
        SQLiteLexicalSurfaces(newer, Catalog((value,)), read_only=True).audit(
            ScopeId("exam-a"), bindings=(value,)
        )


def test_reserved_schema_rejects_forged_ddl_trigger_and_index(tmp_path: Path) -> None:
    value = binding("canonical anatomy")
    (tmp_path / "ddl").mkdir()
    adapter(tmp_path / "ddl", (value,))
    ddl_database = tmp_path / "ddl" / "kb.sqlite3"
    with sqlite3.connect(ddl_database) as connection:
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = replace(sql, ' STRICT', '') "
            "WHERE name = 'kb_lex_receipts'"
        )
        connection.execute("PRAGMA writable_schema = OFF")
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="base table DDL"):
        SQLiteLexicalSurfaces(ddl_database, Catalog((value,)), read_only=True).audit(
            ScopeId("exam-a"), bindings=(value,)
        )

    (tmp_path / "trigger").mkdir()
    adapter(tmp_path / "trigger", (value,))
    trigger_database = tmp_path / "trigger" / "kb.sqlite3"
    with sqlite3.connect(trigger_database) as connection:
        connection.execute(
            "CREATE TRIGGER kb_lex_receipts_trigger AFTER INSERT ON kb_lex_receipts "
            "BEGIN SELECT 1; END"
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="view or trigger"):
        SQLiteLexicalSurfaces(trigger_database, Catalog((value,)), read_only=True).audit(
            ScopeId("exam-a"), bindings=(value,)
        )

    (tmp_path / "index").mkdir()
    adapter(tmp_path / "index", (value,))
    index_database = tmp_path / "index" / "kb.sqlite3"
    with sqlite3.connect(index_database) as connection:
        connection.execute(
            "CREATE INDEX kb_lex_receipts_index ON kb_lex_receipts(catalog_fingerprint)"
        )
        connection.commit()
    with pytest.raises(LexicalIndexIntegrityError, match="unexpected index"):
        SQLiteLexicalSurfaces(index_database, Catalog((value,)), read_only=True).audit(
            ScopeId("exam-a"), bindings=(value,)
        )


def test_search_revalidates_after_first_canonical_catalog_read(tmp_path: Path) -> None:
    initial = binding("canonical anatomy")
    replacement = binding("changed anatomy", revision="revision-b", source="source-b")
    catalog = FlippingCatalog((initial,), (initial,))
    retrieval = SQLiteLexicalSurfaces(tmp_path / "kb.sqlite3", catalog)
    retrieval.index((initial,))
    catalog._replacement = (replacement,)
    catalog.calls = 0
    with pytest.raises(LexicalIndexIntegrityError, match="changed during"):
        retrieval.search(LexicalQuery(ScopeId("exam-a"), "anatomy", LexicalSurface.CANONICAL))
    assert catalog.calls == 4


def test_search_catches_fts_mutation_between_audit_and_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = binding("canonical anatomy")
    retrieval = adapter(tmp_path, (value,))
    original = SQLiteLexicalSurfaces._audit_connection
    calls = 0

    def mutate_after_audit(
        self: SQLiteLexicalSurfaces,
        connection: sqlite3.Connection,
        scopes: tuple[ScopeId, ...],
        expected: tuple[LexicalProjectionBinding, ...],
    ) -> None:
        nonlocal calls
        original(self, connection, scopes, expected)
        calls += 1
        if calls == 1:
            connection.execute(
                "UPDATE lex_canonical SET text = 'tampered' WHERE unit_id = ?",
                (str(value.unit_id),),
            )

    monkeypatch.setattr(SQLiteLexicalSurfaces, "_audit_connection", mutate_after_audit)
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
