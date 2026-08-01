# Log: KB v0.2 offline evidence integration

Date: 2026-08-01 12:00
Area: knowledge-base

## Summary

Integrated the canonical substrate, lineage, document tree, retrievable units,
unitizer, fragments, citation v2, structural/lexical projections, SQLite
lexical surfaces, scopes, retriever registry, and fusion into the active
harness lineage. Added KB-13's offline `EvidenceService`, which turns fused
candidates into separately cited canonical evidence rows without an agent SDK,
transport, planner, or model.

The integration proof starts from a real local Markdown file and verifies:
file bytes -> immutable source revision -> normalized substrate -> admitted
document tree -> unitization -> lexical projection -> SQLite FTS -> registry ->
fusion -> citation-verified `EvidencePacket`.

## Files Changed

- `src/study_agent/domain/evidence.py`: typed evidence packet contracts.
- `src/study_agent/retrieval/evidence.py`: canonical-byte evidence assembly.
- `src/study_agent/knowledge/projections.py`: reconciles KB-06's canonical
  document-root path with tree-root projection validation.
- `tests/integration/test_kb13_evidence_pipeline.py`: real file-to-evidence
  integration proof.
- `pyproject.toml`: makes the repository root available to pytest's test-package
  imports, allowing the KB substrate contract suite to collect consistently.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/unit/knowledge tests/unit/retrieval tests/contract/retrieval tests/architecture/test_knowledge_boundaries.py tests/integration/test_kb13_evidence_pipeline.py`: 468 passed.
- `uv run --python 3.13 --extra dev ruff check src tests`: passed.
- `uv run --python 3.13 --extra dev mypy`: passed (469 files).
- `uv run --python 3.13 --extra dev pytest -q`: 2128 passed, 2 opt-in OpenAI smoke tests skipped.
- `uv build --out-dir /private/tmp/kb-v02-build`: sdist and wheel built successfully.

## Notes

- The partial `_seal` experiment from `kb08` was deliberately excluded: the
  admitted-tree context is already enforced and the partial seal did not add a
  complete guarantee.
- KB-14/15 connector profiles, KB-16 incrementality, figures/items, and model
  adapters remain follow-up beads. The existing `.txt`/`.md` ingestion service
  is the verified baseline source path.
