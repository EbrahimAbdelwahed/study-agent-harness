# Task Bead: HR-10 Sealed verification contracts and leak oracle

Status: Open
Priority: P1
Type: task
Depends On: HR-01-contract-firewall, HR-02-job-store, HR-04-decision-trace

## Outcome

Harness provides portable Reference Exam, Exam Profile, Generation Plan, Synthetic Verification, Coverage Report, novelty, learner-safe views, and opaque presentation-grant contracts. A complete leak oracle blocks sealed question/answer exposure before generation exists.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-10-sealed-contracts.md`: versioned refs, source-revision pins, novelty thresholds, safe views, PresentationGrant, injected validation port, idempotent commands, and leak oracle.
- `specs/future-runtime/README.md`: application-level sealing, opaque host refs, no sealed content in generic paths, and no learner truth in operational state.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-10-sealed-contracts.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a closed serialization, authority, and leak-oracle pass with no generator or web connector. Execute in one fresh Luna xhigh context with a separate security review.

## Context

HR-10 consumes HR-01 authority and PF-05 generic SourceRevisionRef, but it does not import HR-08/09. Sealed means application authority, not an encryption claim. No question or answer bytes may enter generic list/search/export/trace/error paths.

## What To Do

- Add verification contracts/store/view/novelty modules and grant/validation-port commands named by the slice.
- Pin profile/plan/source/scope/objective/prompt/worker/validator versions; implement exact-match and shingle novelty thresholds and two-failure suspension.
- Bind PresentationGrant to revision, opaque host attempt, scope fingerprint, cursor, and expiry; validate through injected port before sealed reads.
- Add nested leak scans for list/search/export/trace/errors/logs/grant commands and unknown-kind fail-closed behavior.

## Likely Files / Packages

- `src/study_agent/verification/contracts.py`, `src/study_agent/verification/store.py`, `src/study_agent/verification/views.py`, `src/study_agent/verification/novelty.py`: sealed schemas and safe views.
- `src/study_agent/verification/presentation.py`, `src/study_agent/ports/presentation_authority.py`: grant/command contracts and injected validation port.
- `tests/unit/verification/test_contracts.py`, `tests/unit/verification/test_novelty.py`: vectors.
- `tests/contract/verification/test_serialization.py`, `tests/contract/verification/test_presentation_grants.py`: codec/idempotency/binding contracts.
- `tests/adversarial/test_sealed_content_leaks.py`: complete leak oracle.

## Acceptance Criteria

- [ ] Schemas, version pins, refs, novelty thresholds, safe views, and grant commands round-trip deterministically; exact/shingle thresholds match HR-10 and two failed regenerations suspend.
- [ ] Grant validation binds revision, opaque attempt, principal-scope fingerprint, cursor, and expiry; injected validation runs before sealed reads; equal idempotency bytes converge and changed bytes fail closed.
- [ ] Lists, search, export, trace, errors, logs, receipts, commands, and unknown view/command kinds contain no questions, answers, raw identity, secrets, or credentials.
- [ ] Focused serialization/leak test gate passes; an independent semantic and security review separately approves authority binding and nested leak coverage; generation remains unavailable.

## Verification

- `.venv/bin/python -m pytest tests/unit/verification/test_contracts.py tests/unit/verification/test_novelty.py tests/contract/verification/test_serialization.py tests/contract/verification/test_presentation_grants.py tests/adversarial/test_sealed_content_leaks.py`: focused gates pass.
- `.venv/bin/python -m pytest`: global offline suite and serialized leak report pass.
- `.venv/bin/python -m ruff check src/study_agent/verification src/study_agent/ports/presentation_authority.py tests/unit/verification tests/contract/verification tests/adversarial/test_sealed_content_leaks.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Cardine authenticity/profile approval, generation workers, web imports, encryption claims, attempts/grades/contests, and edits outside listed paths.

## Invariants

- Sealed content is application-authority protected and absent from all generic views.
- Raw answer text is host-resolved and never enters Harness events, traces, errors, receipts, or views.
- HR-11 is the first slice allowed to generate content.

## Stop Conditions

- Stop if a serializer, grant, error, or test needs raw principal, secret, question, or answer bytes.
- Stop if grant validation needs global identity lookup or self-approval.

## Review Gate

Test/leak and independent semantic/security gates are separate prerequisites for HR-11.

## Notes / Handoff

- HR-11 consumes these contracts and is the only generation workflow bead.
