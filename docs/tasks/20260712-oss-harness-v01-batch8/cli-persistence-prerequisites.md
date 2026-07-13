# Task Bead: cli-persistence-prerequisites Add durable run state, system clock, and catalog reads

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260712-oss-harness-v01-batch8`
Spec: `<spec path>`

## Worker Profile

create `cli-persistence-worker`

Rationale:

No reusable specialization selected yet.

## Context

A process-restart-safe CLI needs production operational state and typed read seams before composition can be credible.

## What To Do

- Implement a path-backed SQLite RunStore with exact create/load/compare-and-set semantics.
- Implement a timezone-aware UTC SystemClock.
- Add deterministic projection-only session listing and only the minimal course enumeration needed by doctor/export.

## Likely Files / Packages

- src/study_agent/adapters/sqlite/run_store.py and adapter exports
- src/study_agent/adapters/system/clock.py and exports
- minimal session/course read-port and projection-view changes
- focused contract and unit tests

## Acceptance Criteria

- [ ] Run state survives reopening and CAS conflicts cannot overwrite newer checkpoints.
- [ ] SystemClock always returns aware UTC datetimes.
- [ ] Catalog reads are deterministic, course-isolated, projection-only, and empty-safe.

## Verification

- `.venv/bin/python -m pytest tests/contract/test_run_store_contract.py tests/contract/session tests/unit/adapters/system`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- CLI commands, export, model composition, provider selection, product work.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
