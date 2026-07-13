# Task Bead: event-state-kernel Implement the event-sourced SQLite state kernel

Status: Completed
Priority: P1
Type: task
Depends On: core-domain-contracts
Run ID: `20260710-oss-harness-v01`
Spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Worker Profile

create `event-state-kernel-worker`

Rationale:

No reusable specialization selected yet.

## Context

ADR-0002 requires the per-course append-only event stream to be canonical, with deterministic reducers and byte-identical replayable projections.

## What To Do

- Implement event type registration and schema-version dispatch.
- Implement a single-writer-per-course SQLite event store with optimistic expected-sequence checks and atomic synchronous projection updates.
- Implement pure deterministic reducers, canonical serialization, projection rebuild, and replay verification.
- Keep snapshots optional and discardable; do not make operational run state authoritative.

## Likely Files / Packages

- `src/study_agent/state/`: registry, reducers, projection state, canonical serialization, replay
- `src/study_agent/adapters/sqlite/`: SQLite event and projection adapter
- `tests/unit/state/`: reducer and serialization tests
- `tests/contract/event_store/`: event-store conformance tests
- `tests/integration/`: atomic append, conflict, rebuild, and replay tests

## Acceptance Criteria

- [x] Canonical mutations append typed events; projection tables have no public direct-write path.
- [x] Event append and synchronous projection update commit or roll back together.
- [x] Per-course sequence conflicts fail explicitly without partial mutation.
- [x] Deleting projections and replaying the same event/reducer versions yields byte-identical canonical serialized state.
- [x] Reducer code is deterministic and side-effect-free.

## Verification

- `python3 -m pytest tests/unit/state tests/contract/event_store tests/integration`: expected to pass or produce documented output
- `python3 -m mypy src/study_agent/state src/study_agent/adapters/sqlite`: expected to pass or produce documented output
- `python3 -m ruff check src/study_agent/state src/study_agent/adapters/sqlite tests/unit/state tests/contract/event_store tests/integration`: expected to pass or produce documented output

## Out Of Scope

- Distributed ordering, multi-writer merge, Postgres, sync, migrations across released schemas, retrieval indexes, and playbook checkpoints.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
