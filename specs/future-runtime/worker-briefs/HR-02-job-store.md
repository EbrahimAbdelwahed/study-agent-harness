# Worker Brief: HR-02

## Assignment

Implement `HR-02-job-store` from `specs/future-runtime/slices/HR-02-job-store.md`.

Worker target: Luna xhigh. Execute only this bead after HR-01 is complete.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-02-job-store.md`
- `specs/future-runtime/beads/HR-02-job-store.md`
- `src/study_agent/jobs/contracts.py`, `src/study_agent/ports/jobs.py`, and current SQLite adapter/test transaction patterns

## Scope

You may change:

- `src/study_agent/adapters/sqlite/job_store.py`
- `src/study_agent/jobs/**`
- `tests/contract/jobs/test_job_store_contract.py`
- `tests/integration/test_sqlite_job_store.py`
- `tests/adversarial/test_job_fencing.py`
- `tests/integration/test_job_recovery.py`

Do not change:

- Paths outside the allowlist, including `SQLiteEventStore`, canonical event code, `RunStore`, lesson-worker stores, executors, trace, flashcards, web/sealed workflows, Cardine, config, and dependencies.

## Requirements

- Implement every HR-02 JobStorePort operation with separate SQLite persistence, deterministic FIFO claims, CAS transitions, lease expiry requeue, increasing fencing tokens, concurrency 8, depth 1, and 64-child limits.
- Preserve queued/lease/attempt/checkpoint/terminal state across kill/reopen and reject stale writes without partial rows.
- Keep in-memory conformance coverage aligned with the port; never write canonical events or product state.

## Acceptance Criteria

- SQLite and in-memory contract tests pass; race/reopen tests prove deterministic recovery and fencing.
- Focused persistence test gate and independent semantic review gate both pass.
- No second lifecycle owner or canonical event-store mutation is introduced.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/contract/jobs/test_job_store_contract.py tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py tests/integration/test_job_recovery.py
.venv/bin/python -m ruff check src/study_agent/adapters/sqlite/job_store.py src/study_agent/jobs tests/contract/jobs tests/integration/test_sqlite_job_store.py tests/adversarial/test_job_fencing.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, behavior implemented, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
