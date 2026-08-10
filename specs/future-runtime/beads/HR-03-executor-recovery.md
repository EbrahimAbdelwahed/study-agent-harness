# Task Bead: HR-03 Executor retry cancellation and resume

Status: Open
Priority: P1
Type: task
Depends On: HR-02-job-store

## Outcome

JobExecutor runs capabilities at least once while owner idempotency commits canonical outcomes exactly once. Transient retry, safe-point cancellation, lease-free suspension, authority-bound resume, and conflicting response rejection are observable and replayable.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-03-executor-recovery.md`: executor seam, retry classifier/backoff, cancellation, suspension, resume-token binding, and owner idempotency.
- `specs/future-runtime/README.md`: retry classes, cancellation semantics, suspended lease rule, and canonical commit ownership.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-03-executor-recovery.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

The executor uses fixed policy and injected ports with scripted failures; no provider specialist is required. Execute in one fresh Luna xhigh context.

## Context

HR-03 adds execution behavior on HR-01/02 without becoming a canonical event writer. Capability executors return validated outcomes, while the domain owner controls canonical commit and idempotency.

## What To Do

- Add `JobExecutor`, retry classification/backoff, and resume-token modules named by the slice.
- Retry only timeout, rate-limit, provider-5xx, and declared-transient failures with maximum three attempts and 1/2/4 second bounded jittered backoff.
- Implement safe-point cancellation, suspension with no lease, authority/input/dependency-bound resume, and changed-byte conflict rejection.
- Add duplicate-delivery, cancellation-after-commit, suspension/restart, and owner-idempotency fixtures.

## Likely Files / Packages

- `src/study_agent/jobs/executor.py`: JobExecutor and owner commit boundary.
- `src/study_agent/jobs/retry.py`: fixed classifier/backoff.
- `src/study_agent/jobs/resume.py`: resume-token codecs and binding validation.
- `tests/unit/jobs/test_executor.py`, `tests/unit/jobs/test_retry_policy.py`: unit policy coverage.
- `tests/integration/test_job_runtime.py`, `tests/integration/test_job_cancellation.py`, `tests/integration/test_job_suspend_resume.py`: scripted runtime flows.
- `tests/adversarial/test_job_duplicate_delivery.py`: duplicate and changed-byte conflicts.

## Acceptance Criteria

- [ ] Only declared transient classes retry, with no more than three monotonic attempts and exact 1/2/4 second policy bounds; validation, authorization, integrity, conflict, and stale failures do not retry.
- [ ] Duplicate delivery with equal canonical bytes converges to one owner commit; changed bytes fail closed; executor never appends a canonical product event directly.
- [ ] Cancellation stops at a safe point, never rolls back a committed event, and reports committed history; suspension holds no lease and resumes from the bound checkpoint.
- [ ] Resume tokens bind Job, attempt, checkpoint, authority, input, and dependencies; stale, expired, scope-mismatch, and changed-response tokens fail closed.
- [ ] Focused runtime test gate passes; an independent semantic review gate confirms retry/canonical-boundary separation.

## Verification

- `.venv/bin/python -m pytest tests/unit/jobs/test_executor.py tests/unit/jobs/test_retry_policy.py tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py`: all focused tests pass.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m ruff check src/study_agent/jobs tests/unit/jobs tests/integration/test_job_runtime.py tests/integration/test_job_cancellation.py tests/integration/test_job_suspend_resume.py tests/adversarial/test_job_duplicate_delivery.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Decision Trace persistence, worker-specific orchestration, web or sealed content, arbitrary retry, rollback, live provider calls, Cardine, and edits outside listed paths.

## Invariants

- Owner idempotency is the only canonical outcome boundary.
- A committed event is never rolled back by cancellation or retry.
- Suspended Jobs hold no lease; resume is authority and fingerprint bound.

## Stop Conditions

- Stop and report if a retry class, canonical writer, or resume field is not fixed in HR-03/README.
- Stop if implementation would expose secrets, raw identity, prompts, or outputs in public errors.

## Review Gate

Focused tests and an independent semantic review must both pass before HR-04 is dispatched.

## Notes / Handoff

- HR-04 consumes executor transition hooks; HR-05 uses this runtime for parity.
