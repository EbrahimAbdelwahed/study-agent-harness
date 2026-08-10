# Task Bead: hr-02-job-store Durable JobStore and fencing

Status: Open
Priority: P1
Type: task
Depends On: hr-01-contract-firewall
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

SQLite JobStore durably owns Job, attempt, queue, lease, heartbeat, child, checkpoint, and terminal state with FIFO claims, CAS transitions, and fencing after expiry.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-02 JobStorePort operations, schema separation, FIFO claims, CAS, fencing, limits, and reopen recovery.
- README durable operational state, owner-only commit, bounded concurrency, and at-least-once execution.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-02-job-store.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Focused SQLite transactions and race fixtures fit one fresh Luna xhigh context.

## Context

HR-02 makes operational Job state durable in a separate database and leaves executor policy to HR-03.

## What To Do

- Add SQLiteJobStore and schema helpers.
- Implement every JobStorePort operation with FIFO, CAS, fencing, concurrency 8, depth 1, and 64-child bounds.
- Add in-memory conformance, race, expiry, stale-fence, and reopen fixtures.

## Likely Files / Packages

- src/study_agent/adapters/sqlite/job_store.py
- src/study_agent/jobs/**
- tests/contract/jobs/test_job_store_contract.py
- tests/integration/test_sqlite_job_store.py
- tests/adversarial/test_job_fencing.py
- tests/integration/test_job_recovery.py

## Acceptance Criteria

- [ ] SQLite and in-memory adapters satisfy JobStorePort with deterministic bytes and no canonical event writes.
- [ ] FIFO/concurrency/child limits and expiry fencing reject stale writes without partial mutation.
- [ ] Focused persistence test gate and independent semantic review gate both pass.

## Verification

- `.venv/bin/python -m pytest tests/contract/jobs/test_job_store_contract.py tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py tests/integration/test_job_recovery.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/adapters/sqlite/job_store.py src/study_agent/jobs tests/contract/jobs tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Executor policy, trace, model/web/flashcard/sealed behavior, canonical event writes, distributed queues, Cardine, RunStore, lesson-worker stores, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
