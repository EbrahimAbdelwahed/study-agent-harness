# Plan: KB v0.2 integration and agent evidence primitives

Date: 2026-08-01 10:30
Area: knowledge-base

## Goal

Integrate the canonical KB spine and offline retrieval slices into the active
Study Agent Harness branch, then expose an offline, typed evidence API that
returns only citation-verified canonical text.

## Scope

- In scope: KB-06, KB-07, KB-08, KB-09A/B, KB-10, KB-11, KB-12, KB-13;
  compatibility with the existing text-source ingestion path; focused tests
  and an end-to-end file-to-evidence proof.
- Out of scope: vector/model/OCR adapters, a transport endpoint, a planner or
  answer synthesis, and unrelated adaptive-tutor changes.

## Approach

1. Cherry-pick the completed KB slices into a clean branch from the active
   head, resolving exports and event registration without replacing active
   harness capabilities.
2. Add model-free KB-13 contracts/service that resolve every primary and
   expansion citation from substrate bytes after fusion.
3. Drive the service from a real local text file through existing immutable
   ingestion, substrate/tree/unit/projection/index/retrieval stages.
4. Run focused, adversarial, integration, typing and lint verification, then
   integrate the resulting commit into the original worktree safely.

## Risks

- KB branches were based on `main`, while the active branch diverged after the
  shared base; imports and registry reducers need explicit reconciliation.
- Index handles are untrusted operational state, so evidence must always
  re-resolve from canonical substrate bytes before it is returned.

## Verification

- Focused KB unit/contract tests, including the file-to-evidence e2e test.
- `ruff check src tests` and strict `mypy` on affected modules.
- Full local pytest suite and package build when practical.
