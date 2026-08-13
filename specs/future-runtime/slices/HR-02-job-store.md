# HR-02 — Durable JobStore and Fencing

## Outcome

Persist Job, attempt, queue, lease, heartbeat, child, checkpoint, and terminal
outcome state in a separate SQLite JobStore with deterministic FIFO claims,
compare-and-set transitions, and fencing after lease expiry.

## Non-goals

No executor policy, model invocation, web evidence, flashcard behavior,
Decision Trace, canonical domain-event writes, distributed queue, or Cardine
schema.

## Contract and API seam

`src/study_agent/ports/jobs.py:JobStorePort` defines create/get/enqueue/claim,
heartbeat, suspend, resume, record-attempt, complete, fail, cancel, stale, and
commit-owner-outcome operations. `src/study_agent/adapters/sqlite/job_store.py:
SQLiteJobStore` owns schema creation, transactional CAS, fencing tokens, and
reopen recovery. JobStore uses its own database path and never writes the
canonical event store.

Lease expiry requeues with an increasing fencing token. Claims are FIFO by
stable queue sequence. Global and per-workflow concurrency are both 8; child
depth is 1 and child count is capped at 64.

## Files and tests

- Add `src/study_agent/adapters/sqlite/job_store.py` and schema helpers under
  `src/study_agent/jobs/`.
- Add `tests/contract/jobs/test_job_store_contract.py`,
  `tests/integration/test_sqlite_job_store.py`,
  `tests/adversarial/test_job_fencing.py`, and
  `tests/integration/test_job_recovery.py`.

## Dependencies

HR-01 contracts; existing `SQLiteEventStore` remains a separate owner. HR-03
depends on this slice.

## Removal condition

No existing `RunStore` or lesson-worker store may gain Job transitions. Those
stores can remain for parity evidence until HR-05/HR-07 removal.

## Review surface

Inspect SQLite schema, transaction boundaries, CAS predicates, fencing-token
increments, queue order, child limits, and database separation. Kill/reopen
tests must prove no lease or terminal transition is silently lost.

## Exact verification

```bash
.venv/bin/python -m pytest tests/contract/jobs/test_job_store_contract.py tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py tests/integration/test_job_recovery.py
.venv/bin/python -m ruff check src/study_agent/adapters/sqlite/job_store.py src/study_agent/jobs tests/contract/jobs tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py
```

Then run full offline pytest and mypy.

## Risks

SQLite transaction races can duplicate claims or lose fencing. Tests must cover
two claimants, expired leases, stale fencing tokens, process reopen, and
compare-and-set failures without partial rows.

## Definition of done

The JobStore contract passes for SQLite and an in-memory test adapter; all
fixed limits and transitions are durable and deterministic; no canonical event
or product state is written; reopen and fencing adversarial tests pass.
