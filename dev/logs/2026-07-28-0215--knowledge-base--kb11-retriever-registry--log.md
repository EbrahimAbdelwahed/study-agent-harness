# Log: KB-11 retriever registry and portable candidates

Date: 2026-07-28 02:15
Area: knowledge-base

## Summary

Implemented the provider-neutral KB-11 retriever seam.  Immutable bounded
manifests, trusted host authority, literal scope queries and filters, portable
candidate provenance, deterministic tie ordering, and structured skip receipts
are now available through `study_agent.ports.retrievers`.

`RetrieverRegistry` snapshots manifests at construction and around every port
call, requires exactly one free/offline `lex_projection` baseline, gates
optional retrievers without invoking skipped ports, and fans out in manifest
identity order.  `LexicalRetriever` bridges each KB-09B lexical surface without
importing SQLite or provider implementations and never leaks indexed text.

## Files Changed

- `src/study_agent/ports/retrievers.py`: bounded immutable retriever contracts.
- `src/study_agent/ports/__init__.py`: public contract exports.
- `src/study_agent/retrieval/registry.py`: immutable authorized registry.
- `src/study_agent/retrieval/lexical.py`: KB-09B lexical bridge.
- `src/study_agent/retrieval/__init__.py`: retrieval exports.
- `tests/unit/retrieval/test_retriever_registry.py`: baseline, gating, filter,
  duplicate, tie, and immutability coverage.
- `specs/kb-v0-2/beads/KB-11-retriever-registry.md`: completion status.

## Verification

- `ruff check ...`: passed.
- `MYPYPATH=src .venv/bin/mypy --strict tests/unit/retrieval/test_retriever_registry.py`: passed.
- `MYPYPATH=src .venv/bin/mypy --strict src/study_agent/ports/retrievers.py src/study_agent/retrieval/lexical.py src/study_agent/retrieval/registry.py`: passed.
- `PYTHONPATH=src pytest -q tests/unit/retrieval/test_retriever_registry.py`: 6 passed.
- `PYTHONPATH=src pytest -q tests/unit/knowledge/test_lexical.py tests/unit/knowledge/test_projections.py tests/unit/knowledge/test_scopes_manifest.py tests/unit/retrieval/test_retriever_registry.py`: 34 passed.

## Notes

- SQLite schema and provider adapters remain out of scope; the bridge consumes
  only the existing `LexicalIndexPort`.
- The integration worktree should run the full suite and architecture tests
  before promotion.

## Review fixes

- Registry manifests are detached into registry-owned snapshots; every live
  manifest is revalidated before a successful batch return.
- `RetrieverSearchBatch` now binds the registry fingerprint and complete
  identity/fingerprint manifest snapshot.
- Equal-score ordering validates recurring scores, and registry size is capped
  before any manifest is read.

## Review verification

- `.../.venv/bin/ruff check src/study_agent/ports/retrievers.py src/study_agent/retrieval/registry.py tests/unit/retrieval/test_retriever_registry.py`: passed.
- `MYPYPATH=src .../.venv/bin/mypy --strict tests/unit/retrieval/test_retriever_registry.py src/study_agent/ports/retrievers.py src/study_agent/retrieval/registry.py`: passed.
- `PYTHONPATH=src pytest -q tests/unit/retrieval/test_retriever_registry.py`: 10 passed.
