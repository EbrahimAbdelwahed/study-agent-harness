# HR-03 — Executor, Retry, Cancellation, and Resume

## Outcome

Run Jobs at least once while committing canonical outcomes exactly once through
owner idempotency. Support bounded transient retries, safe-point cancellation,
suspension without a lease, and authority-bound resume tokens.

## Non-goals

No Decision Trace persistence, worker-specific orchestration, web connector,
flashcard planner, sealed questions, rollback of committed events, or arbitrary
retry of validation/authorization/integrity/conflict/stale failures.

## Contract and API seam

`src/study_agent/jobs/executor.py:JobExecutor` consumes `JobStorePort`, a
clock, cancellation token, and a declared `CapabilityExecutor`. It emits
validated `JobOutcome` values and owner commit requests. Retry is limited to
timeout, rate-limit, provider-5xx, or declared transient failures; maximum
three attempts use 1/2/4 seconds plus bounded jitter. Resume tokens bind Job,
attempt, checkpoint, authority, input, and dependency fingerprints; conflicting
response bytes fail closed.

## Files and tests

- Add `src/study_agent/jobs/executor.py`, `retry.py`, and `resume.py`.
- Add `tests/unit/jobs/test_executor.py`,
  `tests/unit/jobs/test_retry_policy.py`,
  `tests/integration/test_job_runtime.py`,
  `tests/integration/test_job_cancellation.py`,
  `tests/integration/test_job_suspend_resume.py`, and
  `tests/adversarial/test_job_duplicate_delivery.py`.

## Dependencies

HR-01 contracts and HR-02 JobStore. HR-04 consumes executor transition hooks;
HR-05 uses this runtime for lifecycle parity.

## Removal condition

No executor may append a canonical product event directly. The owner commit
port remains the only canonical outcome boundary through all later slices.

## Review surface

Review retry classifier, attempt monotonicity, cancellation checkpoints,
resume-token fingerprinting, owner idempotency, and committed-event behavior.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/jobs/test_executor.py tests/unit/jobs/test_retry_policy.py tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py
```

Then run full offline pytest, Ruff, and strict mypy.

## Risks

Duplicate delivery can produce duplicate canonical effects; owner idempotency
and differing-byte conflict tests must prove convergence. Cancellation after
commit must report committed history rather than pretending rollback.

## Definition of done

Transient failures retry exactly within policy; non-transient failures do not;
duplicate delivery converges; cancellation and suspension are safe; resume
conflicts fail closed; canonical commits are owner-idempotent and replayable.
