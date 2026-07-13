# Task Bead: fts-retrieval Implement portable SQLite FTS5 lexical retrieval

Status: Open
Priority: P1
Type: task
Depends On: source-content-resolver
Run ID: `20260711-oss-harness-v01-batch4`
Spec: `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`

## Worker Profile

create `sqlite-fts-retrieval-worker`

Rationale:

No reusable specialization selected yet.

## Context

Verified retrieval documents can now feed a discardable local lexical index and return exact citations without coupling public contracts to SQLite.

## What To Do

- Refine provider-neutral retrieval document/query/result contracts for filters and immutable ownership.
- Implement SQLite FTS5 unicode61 indexing, metadata upsert, current-revision tracking, BM25 ranking, and deterministic tie-breaks.
- Compile user queries as safe literal tokens and apply all filters before limit.
- Resolve each candidate against SourceContentPort before returning evidence; stale/tampered index rows must fail or be excluded explicitly.
- Add contract, integration, prompt-injection-string, rebuild, and expected-source fixtures.

## Likely Files / Packages

- `src/study_agent/ports/retrieval.py`: portable document/query/result refinements
- `src/study_agent/adapters/sqlite/fts_retrieval.py`: derived lexical index
- `src/study_agent/adapters/sqlite/__init__.py`: explicit adapter export
- `tests/contract/retrieval/`: reusable retrieval behavior
- `tests/integration/test_fts_retrieval.py`: ingestion/index/search/citation/rebuild flow
- `tests/evals/test_lexical_retrieval_fixtures.py`: expected source/chunk fixtures

## Acceptance Criteria

- [ ] Search applies course/revision/kind/role/trust/current filters before limiting.
- [ ] Literal query compilation prevents FTS syntax/control injection.
- [ ] Every result resolves to canonical text and exact citation; row IDs never escape.
- [ ] Ordering is deterministic and index rebuild preserves equivalent public results.
- [ ] No candidates returns insufficient; candidates returns sufficient; conflicting is not fabricated.

## Verification

- `.venv/bin/python -m pytest tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals/test_lexical_retrieval_fixtures.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/ports/retrieval.py src/study_agent/adapters/sqlite/fts_retrieval.py tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/ports/retrieval.py src/study_agent/adapters/sqlite/fts_retrieval.py tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals`: expected to pass or produce documented output

## Out Of Scope

- Vectors, semantic reranking/conflict, prompts, answers, provider calls, canonical state writes, and external frameworks.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
