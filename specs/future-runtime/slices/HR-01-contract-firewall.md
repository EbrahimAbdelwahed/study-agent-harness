# HR-01 — Runtime Contract Firewall

## Outcome

Create the immutable Job, attempt, lease, retry, suspension, resume-token,
trace-reference, web-candidate, and sealed-verification contract vocabulary.
Install adversarial tests before any runtime implementation so a bad lifecycle,
authority, learner-policy field, or sealed-content view fails immediately.

## Non-goals

No SQLite persistence, executor loop, worker, network connector, model call,
Cardine import, curriculum/mastery/readiness/planning field, or learner-facing
question content.

## Contract and API seam

`src/study_agent/jobs/contracts.py` owns `JobId`, `JobState`, `JobRecord`,
`JobAttempt`, `Lease`, `RetryPolicy`, `CheckpointRef`, `ResumeToken`, and
`JobIdentity`. `src/study_agent/ports/jobs.py` owns `JobStorePort` and
`JobExecutorPort`. `src/study_agent/verification/contracts.py` owns opaque
`ReferenceExamRef`, `ExamProfileRef`, `GenerationPlanRef`,
`SyntheticVerificationRef`, and `PresentationReceipt`. `src/study_agent/runtime/
policy_firewall.py` rejects product policy, MODEL authority, unbounded child
plans, unsupported retry classes, and sealed fields in generic views.

Fixed defaults: 60-second lease, 20-second heartbeat, concurrency 8, depth 1,
64 children, at most three attempts, 1/2/4 second backoff, +/-20% jitter, and
30-second cap. Job identity includes capability/version, authority scope,
idempotency key, and input fingerprints; child identity adds parent, position,
and task fingerprint.

## Files and tests

- Add `src/study_agent/jobs/contracts.py`, `src/study_agent/ports/jobs.py`,
  `src/study_agent/runtime/policy_firewall.py`, and
  `src/study_agent/verification/contracts.py`.
- Add `tests/unit/jobs/test_contracts.py`,
  `tests/unit/verification/test_portable_refs.py`,
  `tests/contract/jobs/test_golden_vectors.py`, and
  `tests/adversarial/test_runtime_policy_firewall.py`.
- Add fixtures under `tests/fixtures/jobs/` and
  `tests/fixtures/verification/`; fixtures contain opaque IDs only.

## Dependencies

The released Harness facade and error/authority seams from PF-10/PF-11 are
required. The program orchestrator must also record the PF-11 + CA-10
precondition from the Future Runtime README before dispatching HR-01. That is
an ordering gate only: this slice imports no Cardine package, path, schema, or
test. HR-01 blocks every HR-02–HR-12 implementation slice.

## Removal condition

No separate lifecycle vocabulary may be introduced later. Existing lifecycle,
worker, and lesson checkpoint values remain internal until HR-05/HR-07 parity,
but every new runtime path uses these contracts.

## Review surface

Review state-transition table, identity fingerprints, authority field allowlist,
retry classification, opaque-reference serialization, and the sealed-view deny
list. Confirm no module imports Cardine or product application code.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/jobs/test_contracts.py tests/unit/verification/test_portable_refs.py tests/contract/jobs/test_golden_vectors.py tests/adversarial/test_runtime_policy_firewall.py
.venv/bin/python -m ruff check src/study_agent/jobs src/study_agent/runtime src/study_agent/verification tests/unit/jobs tests/unit/verification tests/contract/jobs tests/adversarial/test_runtime_policy_firewall.py
```

Then run the global offline suite from the README.

## Risks

An overly broad contract can smuggle Cardine policy into Harness or permit
non-deterministic identity. The fixtures must reject unknown policy fields,
MODEL approval, mutable bytes under one identity, and any sealed payload.

## Definition of done

All listed types validate and round-trip deterministically; fixed numeric
defaults have golden vectors; policy and sealed-field adversarial tests pass;
no persistence or worker code is required; the full offline suite stays green.
