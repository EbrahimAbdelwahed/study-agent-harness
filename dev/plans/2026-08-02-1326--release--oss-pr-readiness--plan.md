# Plan: OSS PR readiness

Date: 2026-08-02 13:26 CEST
Area: release

## Goal

Make the audited OSS release-candidate branch mergeable into the repository's
actual default branch and correct its reproducible Linux CI failure without
changing the candidate's approved public boundary.

## Scope

- In scope:
  - inspect PR #7, its push workflow, job logs, and merge conflicts against the
    configured `main` default branch;
  - preserve the contemporary Knowledge Base, Build Week archive, and public
    owner-backed agent tool surface;
  - translate the platform-dependent SQLite response to a forged FTS schema
    into the existing stable integrity-error contract;
  - make `main` an ancestor while keeping the previously audited OSS candidate
    tree authoritative;
  - verify and push only explicit tracked changes on the current OSS branch.
- Out of scope:
  - recall/FSRS, browser or product shells, PDF workarounds, private products,
    and other main-only historical capabilities;
  - changing PR metadata, merging the PR, tags, releases, or package uploads;
  - deleting worktrees or staging existing untracked files.

## Approach

1. Preserve the existing FTS configuration check but perform it before SQLite
   tries to introspect a deliberately invalid virtual table.
2. Run the focused failing contract on supported local Python runtimes, then
   the broader test, lint, typing, packaging, and clean-install gates.
3. Record `origin/main` through an `ours` strategy merge. This resolves the 22
   textual/add-add conflicts without importing the 52 main-only commits that
   violate the approved RC scope; the resulting PR diff will explicitly remove
   those legacy surfaces from `main`.
4. Audit the merge tree, Cardine/private references, staged paths, and untracked
   preservation before pushing.
5. Inspect the new remote workflow through completion and classify any
   remaining failures.

## Risks

- A normal merge would silently union excluded recall, shell, and PDF behavior
  into the candidate. The intentional tree-preserving merge must therefore be
  visible in its commit message and verification log.
- SQLite versions differ in whether malformed FTS DDL can be introspected. The
  fix must order existing validation checks, not broadly catch and relabel all
  operational database errors.
- The working tree contains five unrelated untracked files; every commit must
  use explicit paths and status audits.

## Verification

- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/contract/retrieval/test_sqlite_lexical_surfaces.py`
- `PYTHONPATH=src .venv/bin/python -m pytest -q`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy`
- distribution build/content and clean-wheel smoke commands from CI
- `git merge-tree --write-tree HEAD origin/main`
- tracked-tree private-product and legacy-surface audit
- remote GitHub Actions run and job-log inspection
