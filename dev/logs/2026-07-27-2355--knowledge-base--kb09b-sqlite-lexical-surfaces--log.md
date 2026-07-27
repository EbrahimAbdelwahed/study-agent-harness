# Log: KB-09B SQLite lexical surfaces

Date: 2026-07-27 23:55
Area: knowledge-base

## Summary

Implemented the provider-neutral lexical contracts and a discardable,
scope-local SQLite FTS5 trigram adapter.  The adapter stores projection,
terms, and canonical surfaces separately, but canonical text is validated only
through the KB-03 citation owner and is never returned in a candidate.

## Files Changed

- `src/study_agent/ports/knowledge.py`: typed lexical surfaces, explicit scope
  bindings, literal queries, portable candidates/receipts, and catalog/index
  protocols.
- `src/study_agent/ports/__init__.py`: public port exports.
- `src/study_agent/adapters/sqlite/literal_query.py`: shared versioned query
  compilers (`unicode61-v1` and `medical-trigram-v1`).
- `src/study_agent/adapters/sqlite/fts_retrieval.py`: compatibility delegation
  to the shared v0.1 compiler.
- `src/study_agent/adapters/sqlite/lexical_surfaces.py`: adapter-local schema,
  atomic rebuild, canonical validation, audit, and deterministic search.
- `src/study_agent/adapters/sqlite/__init__.py`: adapter and compiler exports.
- `tests/contract/retrieval/test_sqlite_lexical_surfaces.py`: medical,
  injection, isolation, tie, tampering, rollback, and empty-query coverage.
- `specs/kb-v0-2/beads/KB-09B-sqlite-lexical-surfaces.md`: implementation
  status and binding notes.

## Verification

- `pytest -q tests/contract/retrieval/test_sqlite_lexical_surfaces.py`: 5 passed.
- `pytest -q tests/contract/retrieval/test_sqlite_fts_contract.py`: 20 passed.
- `ruff check` for all changed source/tests: passed.
- strict mypy for changed source files: passed.

## Notes

- The catalog protocol requires `bindings(scope_id)` to return the complete
  active canonical generation.  Explicit index batches are compared against
  that catalog before opening the write transaction.
- The adapter requires SQLite FTS5 trigram with diacritic removal; hosts that
  do not provide it fail during schema initialization rather than silently
  falling back to a different search algorithm.
- Full-suite integration and orchestrator review remain pending.
