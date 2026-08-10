# Log: Integrate adaptive tutor foundation with main

Date: 2026-08-09 17:53 CEST
Area: repository integration

## Summary

Merged the advanced KB v0.2 foundation lineage with `origin/main` without
discarding either history. The resulting branch contains foundation citation,
lineage, structural-unit, lexical-retrieval, registry, fusion, and evidence
work together with main's recall/FSRS, product-shell, capability-gap, PDF
workaround, export v3, and CI work.

The integration also establishes the required worktree/PR contributor workflow,
adds the canonical context map and public roadmap, and fixes an export v3 replay
gap found during independent review. Both source heads are ancestors of the
integration branch. The original dirty checkout was not modified.

Before publication, GitHub `main` had advanced to `6f51c58`. That lineage was
merged as a third parent source: its public agent-operation surface, release
metadata, FTS portability fix, OSS policies, and Build Week archive were kept.
Its release-only removal of recall, FSRS, export v3, capability-gap outbox,
PDF workarounds, and browser shell was intentionally not accepted because the
integration objective requires preserving those verified features. Optional
ports now load lazily so the expanded core remains dependency-light.

## Files Changed

- `AGENTS.md`: requires dedicated `codex/*` worktrees, verification, push, and
  a pull request to `main` for future write tasks.
- `src/study_agent/`, `tests/`, `specs/`, `docs/`, and `pyproject.toml`:
  semantically reconciled the two source lineages, preserving additive public
  contracts, optional extras, entry points, and architecture assertions.
- `src/study_agent/application/export.py`: teaches export v3 replay about KB
  substrate, source-succession, and scope events while preserving EventStore-only
  envelope verification.
- `tests/contract/export/test_kb_v02_export_v3.py`: covers export of valid KB
  v0.2 substrate, succession, configuration, and membership events.
- `CONTEXT.md`, `CONTEXT-MAP.md`, `ROADMAP.md`, and `README.md`: define the
  vocabulary, implemented invariants, approved target, gaps, ordered future
  work, and the `0.2.0` alpha status without creating feature specs or beads.

## Verification

- `git merge-base --is-ancestor 12451cb HEAD`: passed.
- `git merge-base --is-ancestor e18f670 HEAD`: passed.
- Focused conflict-resolution suite: `324 passed`; targeted Ruff and mypy
  passed.
- `uv run --python 3.13 --extra dev pytest -q tests/contract/export`: `21
  passed`.
- `uv run --python 3.13 --extra dev ruff check src tests`: passed.
- `uv run --python 3.13 --extra dev mypy`: passed with `526 source files`.
- `uv run --python 3.13 --extra dev pytest -q`: `2281 passed, 3 skipped`.
  The skips are the documented optional PDF-containment and live-model smoke
  tests.
- `uv build --out-dir /private/tmp/study-agent-final-build.aRK2jv
  --no-create-gitignore --no-build-logs`: built the `0.2.0` sdist and wheel.
- Fresh temporary virtualenv install of the built wheel followed by
  `study-agent --json describe` and `study-agent-shell --help`: passed.
- Independent semantic review found the export replay gap; the fix and its
  documentation corrections received a second review with no remaining
  actionable findings.
- `git diff --check`: passed.
- After merging GitHub `main`, focused public-operation/recall/export/feedback
  verification passed with `124 passed`, followed by `38 passed` for optional
  port lazy-loading and boundary coverage.
- Final `uv run --python 3.13 --extra dev ruff check src tests`: passed.
- Final `uv run --python 3.13 --extra dev mypy`: passed with `530 source files`.
- Final `uv run --python 3.13 --extra dev pytest -q`: `2307 passed, 5 skipped`;
  three skips are optional platform/network smoke tests and two are distribution
  tests that require fresh artifacts.
- `uv build --out-dir dist --no-create-gitignore --no-build-logs` followed by
  `STUDY_AGENT_REQUIRE_DIST=1 ... pytest -q
  tests/quality/test_distribution_contents.py`: `4 passed`.
- Fresh-wheel `study-agent --version`, `study-agent --json describe`,
  `study-agent-shell --help`, and `docs/examples/external_agent.py`: passed.

## Notes

- The core remains dependency-light. FSRS, PDF, provider, and development
  dependencies remain optional extras; no Pi/runtime dependency was added.
- The configured `origin` remains a local filesystem mirror. A separate
  `github` remote targets `EbrahimAbdelwahed/study-agent-harness` so publication
  does not rewrite or disturb the local mirror.
