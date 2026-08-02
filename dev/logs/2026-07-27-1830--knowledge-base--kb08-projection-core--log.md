# Log: KB-08 projection core and structural projector

Date: 2026-07-27 18:30
Area: knowledge-base

## Summary

Implemented strict, versioned, provider-neutral projection contracts and a
deterministic structural projector. Projection rows live in a separate
discardable state map; deletion and projector-version invalidation preserve
canonical units/events. Tree admission now hashes and fully re-derives the
persisted tree before any projection trusts its spans.

## Files Changed

- `src/study_agent/domain/projections.py`: bounded codecs and identities for
  `IndexProjection`, `ProjectionId`, `ProjectionRef`, `ProjectorManifest`, and
  `ProjectorPort`.
- `src/study_agent/knowledge/projections.py`: structural projector, input
  fingerprinting, projection reducer, delete/rebuild helpers.
- `src/study_agent/knowledge/tree.py`: canonical substrate tree admission gate.
- `src/study_agent/domain/__init__.py`, `src/study_agent/knowledge/__init__.py`:
  focused public exports.
- `tests/unit/knowledge/test_projections.py`: bounds, codec, forgery,
  deterministic projector, admission, and delete/rebuild coverage.
- `tests/architecture/test_knowledge_boundaries.py`: ownership and offline
  dependency checks.
- `specs/kb-v0-2/beads/KB-08-projection-core.md`: marked acceptance complete.

## Verification

- `PYTHONPATH=src:. pytest -q tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py`: 336 passed.
- `ruff check` on all changed source/tests: passed.
- `/private/tmp/study-agent-kb/.venv/bin/mypy` on changed source/tests: no issues found.

## Notes

- No model, provider, network, SQLite, corpus-IDF, embeddings, or retrieval
  ranking behavior was added.
- Projection text is not part of `RetrievableUnit` or any citation contract.
- Post-review hardening now requires admitted BODY `TreeNode` ancestors only,
  canonical-unit existence during reduction, bounded finite policy fingerprints,
  deterministic truncation for long headings, and exact projector name/version
  invalidation. Strict mypy passes in the repository's KB environment.
- Follow-up hardening replaces caller-supplied ancestors with the sealed
  `AdmittedDocumentTree` returned by full canonical tree admission. Structural
  projection now resolves BODY ancestors from the admitted tree, checks text
  substrate identity (while resolving figure paths without inventing text
  evidence), and fingerprints admitted metadata plus exact derived nodes.
- `reduce_projections` and canonical unit decoding now accept an explicit
  keyword-only `unitizer_version` context; no version inference is performed.

## Follow-up Verification

- `PYTHONPATH=src:. pytest -q tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py`: 345 passed.
- `ruff check` on changed source/tests: passed.
- `/private/tmp/study-agent-kb/.venv/bin/mypy` on changed source/tests: no issues found.
- `git diff --check`: passed.
