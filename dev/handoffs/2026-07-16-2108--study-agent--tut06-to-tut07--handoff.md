# Handoff: TUT-06 through TUT-07

Date: 2026-07-16 21:08
Area: study-agent

## Current State

TUT-05 is complete and full-gate green. TUT-06A is complete and committed at
`fae32f7`. The active goal remains TUT-04 closure plus TUT-06 and TUT-07.

## Completed

- TUT-04 verified proof conversion, owner publication, and restart-safe runtime composition.
- TUT-05A–E, including proof-bound free-text grades and replayable learner evidence.
- TUT-06A provider-neutral host context and decision boundary.

## Remaining

1. TUT-06B (medium): brief plan, bounded scripted runner, targeted tests, one semantic review.
2. TUT-06C (medium/high file trust boundary): review then immutable host-file snapshots.
3. TUT-06D (high): official OpenAI docs preflight, plan review, optional Responses adapter, independent tests.
4. TUT-06E (medium): scripted demo/closure and milestone full gates.
5. TUT-07A/B/C (high public policy/external FSRS/event sourcing) then TUT-07D (medium closure).
6. TUT-04F headless cross-owner readiness story and final parent-status cleanup.

## Important Context

- Apply the user's risk-proportional workflow; do not create duplicate subagent reviews or artifacts.
- FSRS remains an optional exact extra (`fsrs==6.3.1` per approved spec), never canonical state; replay uses persisted results.
- Do not touch `sbobby-web`; do not use Claude.
- Preserve unrelated dirty TUT-04/capability-gap documents unless deliberately integrated.

## Verification

- `PYTHONPATH=.:src .venv/bin/pytest -q`: 1526 passed, 2 skipped at TUT-05 closure.
- TUT-06A focused: 25 passed.
