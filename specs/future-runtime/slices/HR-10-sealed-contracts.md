# HR-10 — Sealed Verification Contracts and Leak Oracle

## Outcome

Define portable Reference Exam, Exam Profile, Generation Plan, Synthetic Verification, Coverage Report, novelty, and learner-safe presentation schemas. Install a complete leak oracle before any generator creates question data.

## Non-goals

No Cardine authenticity/profile approval, attempt/grade/contest, generation worker, network connector, encryption claim, or learner-model input.

## Contract and API seam

`src/study_agent/verification/contracts.py` owns immutable opaque refs and
version pins for profile, plan, generic `SourceRevisionRef` values from
Package Foundation PF-05, scope/objective refs, prompt/worker/validator
versions, and presentation receipt. HR-10 consumes only that generic source
revision contract; it does not import WebEvidencePort, broker, connector, or
HR-08/HR-09 code. `SealedVerificationStore` holds sealed payloads; generic
list/search/export/trace/error serializers use `LearnerSafeVerificationView`
and never expose questions or answers before an attempt. Novelty rules: exact
match regenerates; five-token-shingle Jaccard >=0.75 regenerates; 0.55–0.75
is uncertain and regenerates; two failed regenerations suspend.

The sealed presentation authority protocol is part of this contract. A
host-issued opaque `PresentationGrant` is bound to exactly:
`verification_revision`, opaque host `attempt_id`,
`principal_scope_fingerprint`, non-negative `cursor`, and `expires_at`. The
grant has no raw principal, credential, secret, question, or answer bytes. An
injected `PresentationAuthorityPort.validate_grant(grant, command_kind,
expected_revision, now)` validates scope, revision, cursor, expiry, and
attempt ownership before any sealed read. It is the only authority check; no
global identity lookup is allowed.

The port accepts idempotent `RevealGrantCommand`, `AnswerGrantCommand`, and
`FinalizeGrantCommand`, each carrying the opaque grant, an idempotency key,
and the expected verification revision/cursor. `AnswerGrantCommand` carries
only an opaque host answer reference and answer commitment; raw answer text is
resolved by the injected host port and never enters Harness events, traces,
errors, receipts, or generic views. Same key and canonical bytes return the
same result; same key with different bytes fails closed.

## Files and tests

- Add verification contracts/store/view/novelty modules and the sealed
  presentation grant/validation-port contracts.
- Add `tests/unit/verification/test_contracts.py`, `tests/unit/verification/test_novelty.py`, `tests/contract/verification/test_serialization.py`, and `tests/adversarial/test_sealed_content_leaks.py`.
- Add `tests/contract/verification/test_presentation_grants.py` covering
  revision/attempt/scope/cursor/expiry binding, idempotency, and raw-answer
  non-disclosure.

## Dependencies

HR-01 authority/firewall, HR-02 storage, HR-04 trace redaction, and the
Package Foundation PF-05 generic `SourceRevision` contract. HR-11 implements
workflow. HR-10 has no dependency on WebEvidencePort, HR-08, or HR-09.

## Removal condition

No generic artifact/export/search/trace path retains a sealed-content bypass. Temporary serializer adapters are removed once all views use the safe view.

## Review surface

Run leak oracle against list, search, export, trace, errors, logs, grant
commands, presentation DTOs, and nested serialization with adversarial
identity/secret/question/answer markers. Unknown view/command kinds fail
closed.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/verification/test_contracts.py tests/unit/verification/test_novelty.py tests/contract/verification/test_serialization.py tests/adversarial/test_sealed_content_leaks.py
```

Then run full offline suite and inspect the serialized leak report.

## Risks

Application-level sealing can be mistaken for cryptographic secrecy. A newly added view can leak content; the oracle fails closed on unknown view kinds.

## Definition of done

Schemas/version pins round-trip deterministically; novelty vectors match
thresholds; grant validation is revision/attempt/scope/cursor/expiry-bound and
idempotent; safe views contain no sealed markers or raw identity/secret/answer;
generation remains impossible until HR-11.
