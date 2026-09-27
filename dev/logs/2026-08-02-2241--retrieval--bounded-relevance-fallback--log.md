# Log: Bounded relevance retrieval fallback

Date: 2026-08-02 22:41
Area: Study Agent Harness retrieval

## Summary

Propagated the shared retrieval correction used by Cardine. SQLite FTS now
prefers exact source-title matches and falls back from strict literal AND to a
bounded, deterministic relevance query over a small set of informative terms.
All canonical course, revision, supersession, kind, role, and trust filters
remain enforced. Central query and result limits bound work before the adapter.

## Files Changed

- `src/study_agent/adapters/sqlite/fts_retrieval.py`: exact-title-first and bounded relevance retrieval.
- `src/study_agent/adapters/sqlite/literal_query.py`: reusable inert unicode61 tokenization.
- `src/study_agent/ports/retrieval.py`: central query and limit bounds.
- `tests/evals/test_lexical_retrieval_fixtures.py`: relevance, title, weak-match, verbose-query, and injection fixtures.
- `tests/contract/retrieval/test_sqlite_fts_contract.py`: central bounds contract.

## Verification

- `uv run pytest -q tests/evals/test_lexical_retrieval_fixtures.py tests/contract/retrieval/test_sqlite_fts_contract.py`: 27 passed.
- `uv run pytest -q`: 2167 passed, 4 skipped.
- `uv run --frozen --extra dev python -m ruff check .`: passed.
- `uv run --frozen --extra dev python -m mypy`: passed.
- Independent correctness review: no remaining MEDIUM+ findings.
- Independent security review: no remaining MEDIUM+ findings.

## Notes

- Public schema fingerprints were preserved; runtime limits live in the central `RetrievalQuery` contract.
- Cardine-specific model routing remains in Cardine because the Harness core does not own the product decision prompt.
- GitHub issue `EbrahimAbdelwahed/study-agent-harness#8` documents the cross-repository problem and adopted solution.
