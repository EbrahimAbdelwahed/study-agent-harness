# Plan: Build Week archive and worktree consolidation

Date: 2026-08-02 12:00 CEST
Area: repository hygiene / Build Week archive

## Goal

Leave the Study Agent Harness primary checkout as the sole worktree, retain the
lightweight Build Week record in one clear in-repository archive, relocate
heavy demo media to a user-accessible external archive, and preserve or
integrate every verified useful worktree change without changing runtime,
demo CLI, or product tests.

## Scope

- In scope: Git audit, document relocation, link updates, media relocation,
  reviewed integration, local commits, and verified local worktree/branch
  removal.
- Out of scope: downstream-product changes, remote actions, README positioning copy,
  runtime/demo/test behavior, and object-database pruning.

## Approach

1. Record every worktree's SHA, merge-base, exclusive commits, tracked diff,
   untracked inventory, and relationship to the primary checkout.
2. Create `docs/archive/build-week/` and move only lightweight Build Week
   documentation into it; update only internal documentation references.
3. Move `output/` media to a named external archive after recording an
   inventory and checksums; verify no media remains Git-untracked.
4. Integrate only a clean, demonstrably useful worktree branch with a
   reversible local merge/cherry-pick and focused verification. Preserve
   ambiguous local changes in place until separately classified.
5. Remove a worktree/branch only after its commit and working-tree uniqueness
   has been proved absent or preserved, then run final repository and test
   checks.

## Risks

- The primary checkout has pre-existing uncommitted Build Week material and
  must not be reset, stashed, or overwritten.
- KB-08 has an intentionally incomplete local anti-forgery patch; it cannot
  be discarded without an explicit preservation decision.
- OSS adoption and public-surface branches may overlap or conflict with the
  active adaptive-tutor branch.

## Verification

- `git diff --check` and `git status --short`
- worktree/ref/commit ancestry and uniqueness audit before every removal
- archive reference scan and external-media manifest/checksum verification
- existing focused Python checks selected from project scripts/configuration
