# Worker Brief: HR-03

## Assignment

Implement `HR-03-executor-recovery` from `specs/future-runtime/slices/HR-03-executor-recovery.md`.

Worker target: Luna xhigh. Execute only this bead after HR-02 is complete.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-03-executor-recovery.md`
- `specs/future-runtime/beads/HR-03-executor-recovery.md`
- `src/study_agent/jobs/contracts.py`, `src/study_agent/ports/jobs.py`, and HR-02 JobStore implementation/tests

## Scope

You may change:

- `src/study_agent/jobs/executor.py`
- `src/study_agent/jobs/retry.py`
- `src/study_agent/jobs/resume.py`
- `tests/unit/jobs/test_executor.py`
- `tests/unit/jobs/test_retry_policy.py`
- `tests/integration/test_job_runtime.py`
- `tests/integration/test_job_cancellation.py`
- `tests/integration/test_job_suspend_resume.py`
- `tests/adversarial/test_job_duplicate_delivery.py`

Do not change:

- Paths outside the allowlist, including canonical event writers, Decision Trace storage, workers, web/sealed flows, Cardine, provider dependencies, and public contracts not named by HR-03.

## Requirements

- Retry only timeout, rate-limit, provider-5xx, and declared-transient failures, using at most three monotonic attempts with 1/2/4s bounded jitter and 30s cap.
- Enforce safe-point cancellation, no lease while suspended, authority/input/dependency-bound resume, and owner-idempotent canonical commit.
- Equal duplicate bytes converge; changed bytes conflict; post-commit cancellation never rolls back history.

## Acceptance Criteria

- Focused executor/retry/suspend/duplicate tests pass and prove non-transient failures do not retry.
- Separate focused test and independent semantic review gates both pass; executor never appends canonical events directly.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/jobs/test_executor.py tests/unit/jobs/test_retry_policy.py tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py
.venv/bin/python -m ruff check src/study_agent/jobs tests/unit/jobs tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, behavior implemented, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
