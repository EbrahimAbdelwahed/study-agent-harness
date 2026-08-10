# Task Bead: hr-03-executor-recovery Executor retry cancellation and resume

Status: Open
Priority: P1
Type: task
Depends On: hr-02-job-store
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

JobExecutor runs capabilities at least once with owner-idempotent canonical commit, bounded transient retry, safe cancellation, lease-free suspension, and authority-bound resume.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-03 executor seam, retry/backoff, cancellation, suspension, resume binding, and owner idempotency.
- README retry classes, cancellation, suspended lease, and canonical commit ownership.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-03-executor-recovery.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Injected ports and scripted failures fit one fresh Luna xhigh context without provider specialization.

## Context

HR-03 adds execution behavior while owner idempotency remains the only canonical boundary.

## What To Do

- Add executor, retry, and resume modules.
- Implement fixed retry classifier/backoff, safe cancellation, suspension, bound tokens, and duplicate delivery handling.
- Add post-commit cancellation and changed-byte conflict fixtures.

## Likely Files / Packages

- src/study_agent/jobs/executor.py
- src/study_agent/jobs/retry.py
- src/study_agent/jobs/resume.py
- tests/unit/jobs/test_executor.py
- tests/unit/jobs/test_retry_policy.py
- tests/integration/test_job_runtime.py
- tests/integration/test_job_cancellation.py
- tests/integration/test_job_suspend_resume.py
- tests/adversarial/test_job_duplicate_delivery.py

## Acceptance Criteria

- [ ] Only declared transient errors retry at most three times with 1/2/4s bounded policy; non-transient errors do not.
- [ ] Equal duplicate bytes converge, changed bytes conflict, cancellation never rolls back committed history, and resume binds all fingerprints.
- [ ] Focused executor test gate and independent semantic review gate both pass.

## Verification

- `.venv/bin/python -m pytest tests/unit/jobs/test_executor.py tests/unit/jobs/test_retry_policy.py tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/jobs tests/unit/jobs tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Trace persistence, worker orchestration, web/sealed content, arbitrary retry, rollback, live providers, Cardine, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
