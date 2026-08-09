# Handoff: Build Week archive and worktree consolidation

Date: 2026-08-02 12:30 CEST
Area: repository hygiene / OSS boundary

## Current State

The Build Week historical record is archived in the Harness repository, the
heavy media are outside it, and one provably redundant worktree is removed.
The requested zero-worktree end state is intentionally pending a product-scope
decision and preservation decision described below.

## Completed

- Committed `98bbdf4` (`docs: archive Build Week materials`), placing the
  lightweight Build Week record under `docs/archive/build-week/`.
- Moved 19 Build Week media files (about 58 MB) without transcoding or deletion
  to a separate, non-versioned media archive.
- Recorded SHA-256 values for the principal media in the archive README;
  `output/` is absent from Harness and no longer appears as Git noise.
- Removed `.tmp-api-repo/` after proving it was not a Git repository and held
  only an API-test lock and runtime JSON.
- Removed clean duplicate worktree and local branch `codex/public-tool-surface`.
- Verified the downstream product only in read-only mode: it is an independent
  checkout whose `.git` is not shared with Harness.
- Scanned the maintained Harness ref and remaining worktree refs for downstream
  product naming: no hits.

## Remaining

- Decide whether the generic public API/release surface in
  `codex/oss-adoption-release` and the canonical operations plus private-name
  cleanup in `codex/public-tool-surface-main` should be reconciled into the
  active adaptive-tutor branch. Both are generic by term scan, but each is a
  large divergent implementation with extensive merge conflicts.
- After those gates, perform a new commit/diff/untracked audit and remove the
  four remaining worktrees and their branches only when every exclusive change
  is integrated or explicitly preserved.

## Important Context

- Do not touch the separate downstream product while completing this Harness
  task.
- Do not delete, reset, or overwrite the pre-existing modified `README.md` or
  unrelated untracked files in the primary checkout.
- Do not merge the release or tool-surface branch merely to remove worktrees:
  they contain major core choices, not mechanical cleanup.

## Verification

- `node --check docs/archive/build-week/proof/app.js`: passed.
- `node --check docs/archive/build-week/proof/flywheel-app.js`: passed.
- `jq empty docs/archive/build-week/proof/demo-data.json`: passed.
- `jq empty docs/archive/build-week/proof/flywheel-data.json`: passed.
- `git diff --check HEAD^ HEAD`: passed.
