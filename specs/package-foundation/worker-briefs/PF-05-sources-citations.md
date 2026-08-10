# Worker Brief: PF-05

## Assignment

Implement `PF-05` from `specs/package-foundation/slices/PF-05-sources-citations.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-03/PF-04/PF-05 slices, and `specs/package-foundation/beads/PF-05-sources-citations.md`
- existing source, ingestion, citation, blob, and replay modules/tests

## Scope

You may change:

- `src/study_agent/api/sources.py`, `src/study_agent/domain/source.py`, `domain/citation_v2.py`
- `src/study_agent/knowledge/citation.py`, `knowledge/projections.py`, `ports/source_input.py`
- `src/study_agent/ingestion/identity.py`, `ingestion/service.py`, `adapters/filesystem/source_input.py`
- `tests/contract/source_content/**`, `tests/contract/sources/**`, source integration tests, and citation unit tests

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, product policy, web connectors, providers, parsers, OCR/PDF/embedding dependencies, CLI/UI, or arbitrary path discovery

## Invariants and Requirements

- Keep logical source, immutable revision, raw blob, normalized substrate, citation, and derived projection identities separate and lineage-linked.
- Expose only `SourceEvidence`, `LearningEvidence`, `RetentionObservation`, and `CandidateWebEvidence`; do not publish bare `Evidence`.
- Verify citation source/revision/unit/substrate, non-empty code-point bounds, and quoted SHA-256 against Host-supplied canonical bytes.
- Preserve historical citations through supersession and reject missing, corrupt, stale, out-of-unit, unsupported, mismatched, or derived-primary evidence.
- Harness accepts bytes or a Host-owned source input port and never scans directories or admits live web content.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/source_content tests/contract/sources tests/unit/knowledge/test_citation_v2.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_source_content_resolution.py tests/integration/test_source_projection_replay.py tests/integration/test_text_ingestion.py
uv run --python 3.13 --extra dev ruff check src/study_agent/domain/source.py src/study_agent/domain/citation_v2.py src/study_agent/knowledge src/study_agent/ingestion src/study_agent/api/sources.py tests/contract/sources
git diff --check
```

## Report Back

Return files changed, source/citation/replay behavior, exact verification,
profile constraints followed, unresolved questions, and follow-up beads.
