# Task Bead: HR-02 Durable JobStore and fencing

Status: Open
Priority: P1
Type: task
Depends On: HR-01-contract-firewall

## Outcome

SQLite JobStore durably owns Job, attempt, queue, lease, heartbeat, child, checkpoint, and terminal-outcome state with deterministic FIFO claims, compare-and-set transitions, and fencing after lease expiry. An in-memory adapter proves the same port contract.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-02-job-store.md`: JobStorePort operations, schema separation, FIFO claims, CAS, fencing, limits, and reopen recovery.
- `specs/future-runtime/README.md`: durable operational state, owner-only canonical commit, bounded concurrency, and at-least-once execution.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-02-job-store.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a focused SQLite contract implementation with explicit tables and race fixtures. Execute in one fresh Luna xhigh context.

## Context

HR-02 makes operational Job state durable without touching the canonical event store or any specialized worker store. It consumes HR-01 values, keeps one database owner, and leaves executor policy to HR-03.

## What To Do

- Add `SQLiteJobStore` and narrowly scoped schema helpers under `src/study_agent/jobs/`.
- Implement create/get/enqueue/claim, heartbeat, suspend/resume, attempt, completion, failure, cancellation, stale, and owner-outcome operations through `JobStorePort`.
- Enforce FIFO queue order, global/per-workflow concurrency 8, depth 1, 64 children, compare-and-set predicates, increasing fencing tokens, and separate database paths.
- Add contract, integration, recovery, and adversarial fixtures for concurrent claims, expiry, stale fencing, reopen, and partial-row prevention.

## Likely Files / Packages

- `src/study_agent/adapters/sqlite/job_store.py`: SQLite adapter and transactions.
- `src/study_agent/jobs/**`: schema/serialization helpers only.
- `tests/contract/jobs/test_job_store_contract.py`: port conformance.
- `tests/integration/test_sqlite_job_store.py`, `tests/integration/test_job_recovery.py`: persistence and reopen behavior.
- `tests/adversarial/test_job_fencing.py`: claimant races, expiry, stale fences, and CAS failures.

## Acceptance Criteria

- [ ] SQLite and in-memory adapters satisfy every JobStorePort operation with deterministic canonical bytes and no canonical event-store writes.
- [ ] Claims are FIFO and bounded by global/per-workflow concurrency; child depth/count limits are enforced before rows are created.
- [ ] Lease expiry requeues with an increased fencing token; stale heartbeat/complete/fail calls fail closed without partial mutation.
- [ ] Kill/reopen recovery preserves queued, lease, attempt, checkpoint, and terminal state exactly once.
- [ ] Focused persistence/race test gate passes; an independent semantic review gate confirms database separation and owner-only canonical commit.

## Verification

- `.venv/bin/python -m pytest tests/contract/jobs/test_job_store_contract.py tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py tests/integration/test_job_recovery.py`: all focused tests pass.
- `.venv/bin/python -m ruff check src/study_agent/adapters/sqlite/job_store.py src/study_agent/jobs tests/contract/jobs tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py`: lint passes.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Executor retry/cancellation policy, Decision Trace, model or web calls, flashcard/sealed behavior, canonical event writes, distributed queues, Cardine modules, and edits outside the listed paths.
- Changes to `RunStore`, lesson-worker stores, or specialized lifecycle transitions.

## Invariants

- SQLite JobStore is a separate operational owner and never writes the canonical event store.
- Every CAS predicate includes Job identity, attempt, and fencing token where applicable.
- At-least-once delivery is permitted; canonical exactly-once commit remains an owner operation.

## Stop Conditions

- Stop and report if a required operation needs a new public API, schema owner, dependency, or second lifecycle.
- Stop if a test requires live network, credentials, or Cardine state.

## Review Gate

Focused tests and an independent semantic review must both pass before HR-03 is dispatched.

## Notes / Handoff

- HR-03 consumes this port and persistence behavior; existing specialized stores remain untouched for parity.
