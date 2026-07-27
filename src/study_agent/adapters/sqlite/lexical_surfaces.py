"""Discardable SQLite FTS5 surfaces for KB-09 lexical projections."""

from __future__ import annotations

import sqlite3
import unicodedata
from collections.abc import Sequence
from contextlib import closing, suppress
from hashlib import sha256
from math import isfinite
from pathlib import Path

from study_agent.adapters.sqlite.event_store import SQLiteConnectionGuard, _writable_nofollow_uri
from study_agent.domain.citation_v2 import TextCitationV2
from study_agent.domain.identifiers import ScopeId, UnitId, substrate_id_for
from study_agent.domain.lineage import SelectionStatus
from study_agent.domain.projections import ProjectionId
from study_agent.domain.units import RetrievableUnit, TextSpan
from study_agent.knowledge.citation import text_citation_for, verify_text_citation
from study_agent.knowledge.lexical import tokenize
from study_agent.ports.knowledge import (
    LexicalCandidate,
    LexicalCandidateList,
    LexicalCatalogPort,
    LexicalIndexReceipt,
    LexicalProjectionBinding,
    LexicalQuery,
    LexicalSurface,
)
from study_agent.state.serialization import canonical_json_bytes

from .literal_query import compile_medical_trigram_query

LEXICAL_SCHEMA_VERSION = "sqlite-lexical-schema-v1"
LEXICAL_INDEX_VERSION = "sqlite-fts5-medical-trigram-v1"
_TRIGRAM_DDL = "tokenize='trigram case_sensitive 0 remove_diacritics 2'"
_SURFACE_TABLES = {
    LexicalSurface.PROJECTION: "lex_projection",
    LexicalSurface.TERMS: "lex_terms",
    LexicalSurface.CANONICAL: "lex_canonical",
}
_RECEIPT_TABLE = "kb_lex_receipts"
_BASE_TABLES = {"kb_lex_schema", "kb_lex_bindings", _RECEIPT_TABLE}
_FTS_SHADOW_SUFFIXES = ("_config", "_content", "_data", "_docsize", "_idx")
_BINDING_COLUMNS = (
    "scope_id",
    "projection_id",
    "unit_id",
    "source_id",
    "revision_id",
    "substrate_id",
    "selection_status",
    "scope_member",
    "binding_fingerprint",
)
_SCHEMA_COLUMNS = (
    "schema_name",
    "schema_version",
    "index_version",
    "generation",
    "catalog_fingerprint",
)
_RECEIPT_COLUMNS = (
    "scope_id",
    "schema_version",
    "index_version",
    "generation",
    "catalog_fingerprint",
)


def _scope_generation(scope_id: ScopeId, catalog_fingerprint: str) -> int:
    """Bind a receipt generation to its complete scope catalog."""

    digest = sha256(
        b"study-agent/lexical-generation/v1\0"
        + canonical_json_bytes(
            {"catalog_fingerprint": catalog_fingerprint, "scope_id": str(scope_id)}
        )
    ).digest()
    return max(1, int.from_bytes(digest[:8], "big") & ((1 << 63) - 1))


def _normalise_match_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _expected_table_names() -> set[str]:
    names = set(_BASE_TABLES) | set(_SURFACE_TABLES.values())
    names.update(
        f"{table}{suffix}"
        for table in _SURFACE_TABLES.values()
        for suffix in _FTS_SHADOW_SUFFIXES
    )
    return names


def _global_receipt(
    rows: Sequence[tuple[str, str, str, int, str]],
) -> tuple[int, str]:
    """Derive the legacy global schema fields from per-scope authorities."""

    if not rows:
        return 0, "0" * 64
    fingerprint = sha256(
        b"study-agent/lexical-global-catalog/v1\0"
        + canonical_json_bytes({"scopes": tuple(rows)})
    ).hexdigest()
    return _scope_generation(ScopeId("lexical-global"), fingerprint), fingerprint


class SQLiteLexicalCapabilityError(RuntimeError):
    """The host SQLite build cannot provide the required FTS5 trigram surface."""


class LexicalIndexIntegrityError(RuntimeError):
    """Derived lexical state cannot be re-resolved to canonical KB state."""


def _catalog_fingerprint(bindings: Sequence[LexicalProjectionBinding]) -> str:
    values = tuple(
        sorted(
            (
                str(binding.scope_id),
                str(binding.unit_id),
                str(binding.projection_id),
                binding.fingerprint,
            )
            for binding in bindings
        )
    )
    return sha256(
        b"study-agent/lexical-catalog/v1\0"
        + canonical_json_bytes({"bindings": values})
    ).hexdigest()


def _surface_text(binding: LexicalProjectionBinding, surface: LexicalSurface) -> str:
    projection = binding.projection
    if surface is LexicalSurface.PROJECTION:
        values = (
            projection.handle,
            projection.summary,
            *projection.covers,
            projection.structural_context,
        )
        return " ".join(value for value in values if value is not None and value)
    if surface is LexicalSurface.TERMS:
        return " ".join((*projection.key_terms, *projection.aliases))
    return _verify_canonical_text(binding)


def _verify_canonical_text(binding: LexicalProjectionBinding) -> str:
    unit = binding.unit
    reference = unit.canonical_ref
    if not isinstance(reference, TextSpan):
        raise LexicalIndexIntegrityError("lexical surfaces require text units")
    try:
        if substrate_id_for(binding.substrate_bytes) != reference.substrate_id:
            raise LexicalIndexIntegrityError("substrate bytes do not match the unit")
        text = binding.substrate_bytes.decode("utf-8", errors="strict")
        citation = text_citation_for(
            unit,
            substrate_bytes=binding.substrate_bytes,
            start=reference.start,
            end=reference.end,
            locator="lexical-index-validation",
        )
        if not isinstance(citation, TextCitationV2):
            raise LexicalIndexIntegrityError("text citation owner returned a non-text citation")
        resolved = verify_text_citation(
            citation,
            substrate_bytes=binding.substrate_bytes,
            unit=unit,
            selection_status=binding.selection_status,
        )
    except LexicalIndexIntegrityError:
        raise
    except Exception as error:
        raise LexicalIndexIntegrityError(
            "canonical unit span failed KB-03 verification"
        ) from error
    if resolved.text is None or text[reference.start : reference.end] != resolved.text:
        raise LexicalIndexIntegrityError("canonical unit span does not resolve")
    return resolved.text


def _require_active(binding: LexicalProjectionBinding) -> None:
    if not binding.scope_member:
        raise LexicalIndexIntegrityError("binding is not an active scope member")
    if binding.selection_status is not SelectionStatus.CURRENT:
        raise LexicalIndexIntegrityError("binding belongs to an inactive revision")
    if not isinstance(binding.unit, RetrievableUnit):
        raise LexicalIndexIntegrityError("binding unit is not canonical")
    if binding.projection.unit_id != binding.unit.unit_id:
        raise LexicalIndexIntegrityError("projection and unit identity disagree")
    # Accessing the property performs the strict ProjectionId derivation.
    _ = binding.projection_id
    _verify_canonical_text(binding)


def _binding_row(binding: LexicalProjectionBinding) -> tuple[object, ...]:
    return (
        str(binding.scope_id),
        str(binding.projection_id),
        str(binding.unit_id),
        str(binding.source_id),
        str(binding.revision_id),
        str(binding.substrate_id),
        binding.selection_status.value,
        int(binding.scope_member),
        binding.fingerprint,
    )


class SQLiteLexicalSurfaces:
    """Scope-local FTS5 indexes with canonical re-resolution at every boundary."""

    def __init__(
        self,
        database: str | Path,
        catalog: LexicalCatalogPort,
        *,
        read_only: bool = False,
        connection_identity_guard: SQLiteConnectionGuard | None = None,
    ) -> None:
        self._database = str(database)
        if self._database == ":memory:":
            raise ValueError("SQLiteLexicalSurfaces requires a path-backed database")
        if type(read_only) is not bool:
            raise TypeError("read_only must be a boolean")
        self._read_only = read_only
        self._catalog = catalog
        self._connection_identity_guard = connection_identity_guard
        if not read_only:
            with closing(self._connect()) as connection:
                self._initialize_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        database = self._database
        uri = False
        if self._read_only:
            database = Path(database).absolute().as_uri() + "?mode=ro&immutable=1"
            uri = True
        elif self._connection_identity_guard is not None:
            database = _writable_nofollow_uri(database)
            uri = True

        def opener() -> sqlite3.Connection:
            return sqlite3.connect(database, timeout=30, uri=uri)

        connection = (
            opener()
            if self._connection_identity_guard is None
            else self._connection_identity_guard.connect(opener)
        )
        if not self._read_only:
            connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @staticmethod
    def _initialize_schema(connection: sqlite3.Connection) -> None:
        try:
            connection.isolation_level = None
            connection.execute("BEGIN IMMEDIATE")
            existing = SQLiteLexicalSurfaces._table_names(connection)
            if existing & _expected_table_names() and "kb_lex_schema" not in existing:
                raise LexicalIndexIntegrityError(
                    "reserved lexical tables require one valid schema record"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_lex_schema (
                    schema_name TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    index_version TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    catalog_fingerprint TEXT NOT NULL
                ) STRICT
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_lex_bindings (
                    scope_id TEXT NOT NULL,
                    projection_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    substrate_id TEXT NOT NULL,
                    selection_status TEXT NOT NULL,
                    scope_member INTEGER NOT NULL CHECK(scope_member IN (0, 1)),
                    binding_fingerprint TEXT NOT NULL,
                    PRIMARY KEY(scope_id, projection_id),
                    UNIQUE(scope_id, unit_id)
                ) STRICT
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_lex_receipts (
                    scope_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    index_version TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    catalog_fingerprint TEXT NOT NULL
                ) STRICT
                """
            )
            SQLiteLexicalSurfaces._create_surface(connection, "lex_projection")
            SQLiteLexicalSurfaces._create_surface(connection, "lex_terms")
            SQLiteLexicalSurfaces._create_surface(connection, "lex_canonical")
            row = connection.execute(
                "SELECT schema_version, index_version FROM kb_lex_schema WHERE schema_name = ?",
                (LEXICAL_SCHEMA_VERSION,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO kb_lex_schema(
                        schema_name, schema_version, index_version, generation, catalog_fingerprint
                    ) VALUES (?, ?, ?, 0, ?)
                    """,
                    (
                        LEXICAL_SCHEMA_VERSION,
                        LEXICAL_SCHEMA_VERSION,
                        LEXICAL_INDEX_VERSION,
                        "0" * 64,
                    ),
                )
            elif str(row[0]) != LEXICAL_SCHEMA_VERSION:
                raise ValueError("unsupported lexical schema version")
            elif str(row[1]) != LEXICAL_INDEX_VERSION:
                raise ValueError("unsupported lexical index version")
            SQLiteLexicalSurfaces._validate_schema(connection)
            connection.execute("COMMIT")
        except sqlite3.OperationalError as error:
            with suppress(sqlite3.OperationalError):
                connection.execute("ROLLBACK")
            if "fts5" in str(error).lower() or "tokenize" in str(error).lower():
                raise SQLiteLexicalCapabilityError(
                    "SQLite FTS5 trigram tokenizer is unavailable"
                ) from error
            raise
        except Exception:
            with suppress(sqlite3.OperationalError):
                connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow')"
            ).fetchall()
            if str(row[0]) not in {"sqlite_schema", "sqlite_temp_schema"}
        }

    @staticmethod
    def _reserved_table_names(connection: sqlite3.Connection) -> set[str]:
        names = SQLiteLexicalSurfaces._table_names(connection)
        surfaces = tuple(_SURFACE_TABLES.values())
        return {
            name
            for name in names
            if name.startswith("kb_lex_")
            or name in surfaces
            or any(name.startswith(f"{surface}_") for surface in surfaces)
        }

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
        return tuple(
            str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        )

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        names = SQLiteLexicalSurfaces._reserved_table_names(connection)
        if names != _expected_table_names():
            raise LexicalIndexIntegrityError("lexical schema has unknown or missing tables")
        expected_columns = {
            "kb_lex_schema": _SCHEMA_COLUMNS,
            "kb_lex_bindings": _BINDING_COLUMNS,
            _RECEIPT_TABLE: _RECEIPT_COLUMNS,
        }
        for table, columns in expected_columns.items():
            if SQLiteLexicalSurfaces._columns(connection, table) != columns:
                raise LexicalIndexIntegrityError(f"lexical schema columns are invalid: {table}")
        for table in _SURFACE_TABLES.values():
            if SQLiteLexicalSurfaces._columns(connection, table) != (
                "scope_id",
                "unit_id",
                "projection_id",
                "text",
            ):
                raise LexicalIndexIntegrityError(f"lexical FTS columns are invalid: {table}")
            row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
            ).fetchone()
            sql = "" if row is None or row[0] is None else "".join(str(row[0]).lower().split())
            expected = "".join(
                (
                    f"create virtual table {table} using fts5("
                    "scope_id unindexed, unit_id unindexed, projection_id unindexed, text, "
                    "tokenize='trigram case_sensitive 0 remove_diacritics 2')"
                ).split()
            )
            if sql != expected:
                raise LexicalIndexIntegrityError(f"lexical FTS configuration is invalid: {table}")
        rows = connection.execute(
            "SELECT schema_name, schema_version, index_version, generation, catalog_fingerprint "
            "FROM kb_lex_schema ORDER BY schema_name"
        ).fetchall()
        if len(rows) != 1 or tuple(str(value) for value in rows[0][:3]) != (
            LEXICAL_SCHEMA_VERSION,
            LEXICAL_SCHEMA_VERSION,
            LEXICAL_INDEX_VERSION,
        ):
            raise LexicalIndexIntegrityError("lexical schema receipt is missing, unknown, or stale")
        if type(rows[0][3]) is not int or rows[0][3] < 0:
            raise LexicalIndexIntegrityError("lexical schema generation is invalid")
        fingerprint = str(rows[0][4])
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise LexicalIndexIntegrityError("lexical schema fingerprint is invalid")
        receipt_rows = connection.execute(
            "SELECT scope_id, schema_version, index_version, generation, catalog_fingerprint "
            "FROM kb_lex_receipts ORDER BY scope_id"
        ).fetchall()
        for row in receipt_rows:
            if tuple(str(value) for value in row[1:3]) != (
                LEXICAL_SCHEMA_VERSION,
                LEXICAL_INDEX_VERSION,
            ):
                raise LexicalIndexIntegrityError("lexical scope receipt version is invalid")
            if not str(row[0]).strip() or type(row[3]) is not int or row[3] < 1:
                raise LexicalIndexIntegrityError("lexical scope receipt generation is invalid")
            value = str(row[4])
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise LexicalIndexIntegrityError("lexical scope receipt fingerprint is invalid")
        receipt_state = tuple(
            (str(row[0]), str(row[1]), str(row[2]), int(row[3]), str(row[4]))
            for row in receipt_rows
        )
        expected_generation, expected_fingerprint = _global_receipt(receipt_state)
        if int(rows[0][3]) != expected_generation or fingerprint != expected_fingerprint:
            raise LexicalIndexIntegrityError("lexical global receipt is stale or forged")

    @staticmethod
    def _create_surface(connection: sqlite3.Connection, table: str) -> None:
        if table not in _SURFACE_TABLES.values():
            raise ValueError("invalid lexical surface table")
        connection.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING fts5(
                scope_id UNINDEXED,
                unit_id UNINDEXED,
                projection_id UNINDEXED,
                text,
                {_TRIGRAM_DDL}
            )
            """
        )

    def _require_write(self) -> None:
        if self._read_only:
            raise PermissionError("read-only lexical adapter cannot mutate the index")

    def _resolve_bindings(
        self,
        bindings: Sequence[LexicalProjectionBinding] | None,
        *,
        scope_id: ScopeId | None = None,
    ) -> tuple[LexicalProjectionBinding, ...]:
        if bindings is None:
            if scope_id is None:
                raise TypeError("scope_id is required when bindings are omitted")
            bindings = self._catalog.bindings(scope_id)
        values = tuple(bindings)
        if not values:
            if scope_id is not None:
                # An empty configured scope is a valid complete catalog.
                return ()
            raise ValueError("lexical index requires at least one scope binding")
        seen: set[tuple[str, str]] = set()
        for binding in values:
            if not isinstance(binding, LexicalProjectionBinding):
                raise TypeError("bindings must contain LexicalProjectionBinding values")
            _require_active(binding)
            key = (str(binding.scope_id), str(binding.unit_id))
            if key in seen:
                raise ValueError("one active projection must exist per scope and unit")
            seen.add(key)
            if scope_id is not None and binding.scope_id != scope_id:
                raise ValueError("bindings contain a different scope")
        ordered = tuple(sorted(values, key=lambda item: (str(item.scope_id), str(item.unit_id))))
        # An explicit batch is still checked against the complete canonical
        # catalog; callers cannot accidentally create a partial generation.
        for current_scope in sorted({item.scope_id for item in ordered}, key=str):
            canonical = tuple(self._catalog.bindings(current_scope))
            canonical_ids = tuple(sorted(item.fingerprint for item in canonical))
            supplied_ids = tuple(
                sorted(item.fingerprint for item in ordered if item.scope_id == current_scope)
            )
            if canonical_ids != supplied_ids:
                raise ValueError("lexical index batch must contain the complete canonical scope")
        return ordered

    def index(
        self,
        bindings: Sequence[LexicalProjectionBinding] | None = None,
        *,
        scope_id: ScopeId | None = None,
    ) -> LexicalIndexReceipt:
        """Replace the supplied scope generations atomically."""

        self._require_write()
        batch = self._resolve_bindings(bindings, scope_id=scope_id)
        if not batch:
            if scope_id is None:
                raise ValueError("scope_id is required to index an empty scope")
            scopes: tuple[ScopeId, ...] = (scope_id,)
        else:
            scopes = tuple(sorted({item.scope_id for item in batch}, key=str))
        with closing(self._connect()) as connection:
            connection.isolation_level = None
            try:
                connection.execute("BEGIN IMMEDIATE")
                for current_scope in scopes:
                    self._delete_scope(connection, current_scope)
                for binding in batch:
                    self._insert_binding(connection, binding)
                self._update_receipt(connection, batch, scopes)
                connection.execute("COMMIT")
            except Exception:
                with suppress(sqlite3.OperationalError):
                    connection.execute("ROLLBACK")
                raise
        return self.audit(scopes[0] if len(scopes) == 1 else None, bindings=batch)

    def rebuild(
        self,
        bindings: Sequence[LexicalProjectionBinding] | None = None,
        *,
        scope_id: ScopeId | None = None,
    ) -> LexicalIndexReceipt:
        """Rebuild is intentionally the same atomic replacement operation."""

        return self.index(bindings, scope_id=scope_id)

    @staticmethod
    def _delete_scope(connection: sqlite3.Connection, scope_id: ScopeId) -> None:
        key = str(scope_id)
        connection.execute("DELETE FROM kb_lex_bindings WHERE scope_id = ?", (key,))
        for table in _SURFACE_TABLES.values():
            connection.execute(f"DELETE FROM {table} WHERE scope_id = ?", (key,))

    @staticmethod
    def _insert_binding(connection: sqlite3.Connection, binding: LexicalProjectionBinding) -> None:
        connection.execute(
            """
            INSERT INTO kb_lex_bindings(
                scope_id, projection_id, unit_id, source_id, revision_id, substrate_id,
                selection_status, scope_member, binding_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _binding_row(binding),
        )
        for surface, table in _SURFACE_TABLES.items():
            connection.execute(
                f"INSERT INTO {table}(scope_id, unit_id, projection_id, text) VALUES (?, ?, ?, ?)",
                (
                    str(binding.scope_id),
                    str(binding.unit_id),
                    str(binding.projection_id),
                    _surface_text(binding, surface),
                ),
            )

    @staticmethod
    def _update_receipt(
        connection: sqlite3.Connection,
        bindings: Sequence[LexicalProjectionBinding],
        scopes: Sequence[ScopeId],
    ) -> None:
        for scope_id in scopes:
            scoped = tuple(item for item in bindings if item.scope_id == scope_id)
            fingerprint = _catalog_fingerprint(scoped)
            generation = _scope_generation(scope_id, fingerprint)
            connection.execute(
                """
                INSERT INTO kb_lex_receipts(
                    scope_id, schema_version, index_version, generation, catalog_fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    index_version = excluded.index_version,
                    generation = excluded.generation,
                    catalog_fingerprint = excluded.catalog_fingerprint
                """,
                (
                    str(scope_id),
                    LEXICAL_SCHEMA_VERSION,
                    LEXICAL_INDEX_VERSION,
                    generation,
                    fingerprint,
                ),
            )
        receipt_rows = connection.execute(
            """
            SELECT scope_id, schema_version, index_version, generation, catalog_fingerprint
              FROM kb_lex_receipts ORDER BY scope_id
            """
        ).fetchall()
        receipt_state = tuple(
            (str(row[0]), str(row[1]), str(row[2]), int(row[3]), str(row[4]))
            for row in receipt_rows
        )
        global_generation, global_fingerprint = _global_receipt(receipt_state)
        connection.execute(
            """
            UPDATE kb_lex_schema
               SET index_version = ?, generation = ?, catalog_fingerprint = ?
             WHERE schema_name = ?
            """,
            (
                LEXICAL_INDEX_VERSION,
                global_generation,
                global_fingerprint,
                LEXICAL_SCHEMA_VERSION,
            ),
        )

    def audit(
        self,
        scope_id: ScopeId | None = None,
        *,
        bindings: Sequence[LexicalProjectionBinding] | None = None,
    ) -> LexicalIndexReceipt:
        """Audit derived rows against a complete canonical scope catalog."""

        if bindings is None:
            if scope_id is None:
                raise TypeError("scope_id is required for a lexical audit")
            expected = self._resolve_bindings(None, scope_id=scope_id)
        else:
            expected = self._resolve_bindings(bindings, scope_id=scope_id)
        if scope_id is None:
            scopes = tuple(sorted({item.scope_id for item in expected}, key=str))
        else:
            scopes = (scope_id,)
        with closing(self._connect()) as connection:
            connection.isolation_level = None
            connection.execute("BEGIN")
            try:
                self._audit_connection(connection, scopes, expected)
                connection.execute("COMMIT")
            except Exception:
                with suppress(sqlite3.OperationalError):
                    connection.execute("ROLLBACK")
                raise
        return LexicalIndexReceipt(
            len(expected), LEXICAL_INDEX_VERSION, _catalog_fingerprint(expected)
        )

    def _audit_connection(
        self,
        connection: sqlite3.Connection,
        scopes: Sequence[ScopeId],
        expected: Sequence[LexicalProjectionBinding],
    ) -> None:
        self._validate_schema(connection)
        for current_scope in scopes:
            self._audit_scope(connection, current_scope, expected)
            fingerprint = _catalog_fingerprint(
                tuple(item for item in expected if item.scope_id == current_scope)
            )
            row = connection.execute(
                """
                SELECT schema_version, index_version, generation, catalog_fingerprint
                  FROM kb_lex_receipts WHERE scope_id = ?
                """,
                (str(current_scope),),
            ).fetchone()
            if row is None or tuple(str(value) for value in row[:2]) != (
                LEXICAL_SCHEMA_VERSION,
                LEXICAL_INDEX_VERSION,
            ):
                raise LexicalIndexIntegrityError("lexical scope receipt is missing or stale")
            if type(row[2]) is not int or row[2] != _scope_generation(current_scope, fingerprint):
                raise LexicalIndexIntegrityError("lexical scope generation is stale or forged")
            if str(row[3]) != fingerprint:
                raise LexicalIndexIntegrityError(
                    "lexical scope catalog fingerprint is stale or forged"
                )

    def _audit_scope(
        self,
        connection: sqlite3.Connection,
        scope_id: ScopeId,
        expected: Sequence[LexicalProjectionBinding],
    ) -> None:
        scoped = tuple(item for item in expected if item.scope_id == scope_id)
        expected_bindings = tuple(sorted((_binding_row(item) for item in scoped), key=str))
        rows = tuple(
            connection.execute(
                """
                SELECT scope_id, projection_id, unit_id, source_id, revision_id, substrate_id,
                       selection_status, scope_member, binding_fingerprint
                  FROM kb_lex_bindings WHERE scope_id = ?
                 ORDER BY scope_id, projection_id
                """,
                (str(scope_id),),
            ).fetchall()
        )
        if rows != expected_bindings:
            raise LexicalIndexIntegrityError("lexical binding metadata is stale, missing, or extra")
        for surface, table in _SURFACE_TABLES.items():
            actual = tuple(
                connection.execute(
                    f"""
                    SELECT scope_id, unit_id, projection_id, text
                      FROM {table}
                     WHERE scope_id = ?
                     ORDER BY scope_id, unit_id, projection_id, rowid
                    """,
                    (str(scope_id),),
                ).fetchall()
            )
            expected_surface = tuple(
                sorted(
                    (
                        str(item.scope_id),
                        str(item.unit_id),
                        str(item.projection_id),
                        _surface_text(item, surface),
                    )
                    for item in scoped
                )
            )
            if actual != expected_surface:
                raise LexicalIndexIntegrityError(
                    f"{surface.value} lexical rows are stale, missing, extra, or tampered"
                )

    def search(self, query: LexicalQuery) -> LexicalCandidateList:
        if not isinstance(query, LexicalQuery):
            raise TypeError("query must be LexicalQuery")
        expected = self._resolve_bindings(None, scope_id=query.scope_id)
        compiled = compile_medical_trigram_query(query.text)
        table = _SURFACE_TABLES[query.surface]
        query_tokens = tuple(_normalise_match_text(token) for token in tokenize(query.text))
        with closing(self._connect()) as connection:
            connection.isolation_level = None
            connection.execute("BEGIN")
            try:
                scopes = (query.scope_id,)
                self._audit_connection(connection, scopes, expected)
                rows = () if compiled is None else connection.execute(
                    f"""
                    SELECT unit_id, projection_id, text
                      FROM {table}
                     WHERE {table} MATCH ? AND scope_id = ?
                    """,
                    (compiled, str(query.scope_id)),
                ).fetchall()
                # FTS5 bm25 is corpus-global, so using it would allow an
                # unrelated scope to perturb this scope's ranking.  Re-rank
                # only from the queried row's literal text instead.
                ranked = sorted(
                    rows,
                    key=lambda row: (
                        -sum(
                            _normalise_match_text(str(row[2])).count(token)
                            for token in query_tokens
                        ),
                        str(row[0]),
                        str(row[1]),
                    ),
                )[: query.limit]
                self._audit_connection(connection, scopes, expected)
                after = self._resolve_bindings(None, scope_id=query.scope_id)
                if _catalog_fingerprint(after) != _catalog_fingerprint(expected):
                    raise LexicalIndexIntegrityError(
                        "canonical scope changed during lexical search"
                    )
                connection.execute("COMMIT")
            except Exception:
                with suppress(sqlite3.OperationalError):
                    connection.execute("ROLLBACK")
                raise
        by_identity = {(str(item.unit_id), str(item.projection_id)): item for item in expected}
        resolved: list[tuple[UnitId, ProjectionId, float]] = []
        for row in ranked:
            key = (str(row[0]), str(row[1]))
            binding = by_identity.get(key)
            if binding is None:
                raise LexicalIndexIntegrityError("search returned an unresolvable lexical row")
            raw = float(
                sum(_normalise_match_text(str(row[2])).count(token) for token in query_tokens)
            )
            if not isfinite(raw):
                raise LexicalIndexIntegrityError("search returned a non-finite lexical score")
            resolved.append((binding.unit_id, binding.projection_id, raw))
        scale = max((score for _, _, score in resolved), default=0.0)
        candidates = tuple(
            LexicalCandidate(
                unit_id,
                projection_id,
                rank,
                score / scale if scale else 0.0,
                query.fingerprint,
                LEXICAL_INDEX_VERSION,
            )
            for rank, (unit_id, projection_id, score) in enumerate(resolved, 1)
        )
        return LexicalCandidateList(
            query.surface, query.fingerprint, LEXICAL_INDEX_VERSION, candidates
        )


__all__ = [
    "LEXICAL_INDEX_VERSION",
    "LEXICAL_SCHEMA_VERSION",
    "LexicalIndexIntegrityError",
    "SQLiteLexicalCapabilityError",
    "SQLiteLexicalSurfaces",
]
