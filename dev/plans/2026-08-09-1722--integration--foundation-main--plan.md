# Plan: Integrate adaptive tutor foundation with main

Date: 2026-08-09 17:22 CEST
Area: repository integration

## Goal

Produce one reviewable lineage that preserves the advanced KB v0.2 evidence
pipeline from `codex/adaptive-tutor-foundation` and the recall, product shell,
capability-gap, PDF workaround, export, and CI work from `origin/main`.

## Scope

- In scope:
  - merge `origin/main` into `codex/integrate-foundation-main`;
  - resolve every conflict from primary-source commits and existing contracts;
  - preserve both lineages' public behavior and verification coverage;
  - add `CONTEXT.md`, `CONTEXT-MAP.md`, and `ROADMAP.md` for the approved
    study-harness direction;
  - record verification and obtain an independent semantic review;
  - push the integration branch and open a pull request targeting `main`.
- Out of scope:
  - implementing worker queues, web research, generation workflows,
    observability, evals, or Cardine package consumption;
  - creating feature specs or beads;
  - modifying or cleaning the original dirty worktree.

## Approach

1. Inspect the exclusive commits, affected registries, contracts, tests, and
   prior dev memory for both lineages.
2. Merge `origin/main` without committing, resolve documentation conflicts from
   their milestone truth, and combine code exports/registries additively.
3. Run focused KB, recall, capability-gap/PDF, product-shell, replay, and
   architecture checks before the full quality gates.
4. Write the context glossary, context map, and public roadmap with explicit
   `Current`, `Approved Target`, and `Gap` boundaries.
5. Run Ruff, strict mypy, full pytest, package build, diff checks, and an
   independent semantic review; fix only approved integration findings.
6. Commit the resolved integration and documentation, push the branch, and open
   a pull request to `main`.

## Risks

- Choosing one side of KB conflicts wholesale could regress citation v2,
  lineage, structural units, lexical retrieval, scopes, registry, or fusion.
- Combining domain and port exports mechanically could hide identifier or
  architecture-boundary conflicts.
- `pyproject.toml` may merge textually while still losing scripts, optional
  extras, or package data.
- Product-shell and recall tests may depend on the older KB substrate shape.
- Documentation can overstate approved target workflows as shipped behavior.
- The local `origin` remote is a filesystem mirror rather than GitHub; PR
  publication requires resolving the GitHub push path after local verification.

## Verification

- `git diff --check`
- focused pytest suites for KB, recall, capability-gap/PDF, tutor host, product
  shell, replay, and architecture boundaries
- `uv run --python 3.13 --extra dev ruff check src tests`
- `uv run --python 3.13 --extra dev mypy`
- `uv run --python 3.13 --extra dev pytest -q`
- `uv build --out-dir <temporary-directory>`
- independent semantic/regression review of the completed branch
