# Plan: TUT-07 recall ledger checkpoint

Date: 2026-07-21 19:05
Area: adaptive-tutor

## Goal

Establish the provider-neutral recall identities, strict schema-v1 events,
pure reducers, projection view, and inward scheduling port without importing a
scheduler implementation.

## Scope

- In scope: `domain` recall identifiers, `recall` contracts/events/projection/view,
  and `ports` scheduling/recall exports.
- Out of scope: service commands, due policy, FSRS adapter, export and repository
  composition.

## Verification

- Parent venv focused public/domain tests.
- Python compile/import smoke and `git diff --check`.
