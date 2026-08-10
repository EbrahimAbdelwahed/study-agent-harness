# HR-11 — Sealed Generation, Coverage Review, and Presentation

## Outcome

Run approved profile and accepted plan through generation Jobs, independent coverage review, deterministic release, and progressive presentation. Return only a presentation receipt to Cardine; Cardine owns attempts, responses, criteria, grades, and contests.

## Non-goals

No generator self-review/release, missing-coverage acceptance, automatic academic approval, learner-model computation, exposed pre-attempt questions, or prior-attempt mutation.

## Contract and API seam

`src/study_agent/verification/workflow.py:VerificationWorkflow` creates
generation child Jobs, invokes an independent `CoverageReviewer`, applies the
deterministic release gate, and emits `PresentationReceipt` only after
complete required coverage and zero unsupported claims. Required, partial, or
uncertain coverage blocks release. Source drift stales affected shards; a new
generic `SourceRevisionRef` from PF-05 triggers global review while prior
attempts remain historical. HR-11 consumes only that generic source-revision
contract and has no dependency on WebEvidencePort, HR-08, or HR-09.

Every question pins profile, plan, generic source-revision refs,
scope/objective refs, and prompt/worker/validator versions. The learner sees
an accepted plan and progressive questions only during an authorized attempt;
answers are available after finalization only through the sealed presentation
protocol from HR-10.

Presentation commands are `RevealGrantCommand`, `AnswerGrantCommand`, and
`FinalizeGrantCommand` validated by the injected `PresentationAuthorityPort`.
Each grant is opaque and host-issued, bound to verification revision, opaque
attempt ID, principal-scope fingerprint, cursor, and expiry. Commands are
idempotent by canonical idempotency key and grant bytes. Reveal/finalize
returns only a receipt or safe outcome; answer accepts an opaque host answer
reference/commitment and never serializes raw identity, secret, question, or
answer bytes into events, traces, errors, receipts, or generic views.

## Files and tests

- Add workflow, independent reviewer, release gate, presentation service, and
  injected grant-validation port under `src/study_agent/verification/`.
- Add `tests/integration/test_synthetic_verification_workflow.py`, `tests/integration/test_verification_targeted_regeneration.py`, `tests/integration/test_verification_presentation_receipt.py`, and `tests/adversarial/test_verification_authority.py`.
- Extend the presentation tests with idempotent reveal/answer/finalize grant
  commands, stale/expired/scope-mismatch rejection, and raw-answer leak scans.

## Dependencies

HR-03 executor, HR-04 trace, PF-05 generic `SourceRevision` contracts, HR-10
sealed contracts/leak oracle, and HR-05 lifecycle. HR-11 has no dependency on
HR-08 or HR-09.

## Removal condition

No temporary workflow bypasses the independent reviewer or safe presentation view. Old verified-batch paths are removed or narrowed to the portable receipt after parity.

## Review surface

Review Job graph, reviewer independence, release-gate predicates, stale-shard
regeneration, version pins, attempt history, grant validation, idempotent
command convergence, and pre/post-attempt safe views. Confirm raw identity,
secrets, and answers never cross the injected validation port.

## Exact verification

```bash
.venv/bin/python -m pytest tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py
```

Then run full offline suite and inspect deterministic workflow/release reports.

The presentation integration test must prove the grant binding tuple
`(verification_revision, attempt_id, principal_scope_fingerprint, cursor,
expires_at)`, injected-port validation before sealed reads, same-key
idempotency, different-byte conflict, and leak-free receipts/traces/errors.
The shared release gate is not published here: HR-12 alone publishes the
`1.4` final aggregate.

## Risks

The generator may omit required coverage or a reviewer may share generator state. Fixtures force missing/partial/uncertain outcomes, unsupported claims, drift, duplicate attempts, and reviewer/generator separation.

## Definition of done

Only approved profile + accepted plan starts generation; independent review and
complete deterministic coverage gate release; novelty failures suspend without
exposing content; grant commands are revision/attempt/scope/cursor/expiry
bound and idempotent; raw identity/secret/question/answer data never leaks;
receipt and historical attempts are correct; leak oracle passes; HR-12 alone
publishes the `1.4` final aggregate.
