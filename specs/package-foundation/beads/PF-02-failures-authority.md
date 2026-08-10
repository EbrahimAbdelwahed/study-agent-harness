# Task Bead: PF-02 Failures and authority

Status: Open
Priority: P1
Type: task
Depends On: PF-01

## Outcome

Public calls use one closed `HarnessError` taxonomy and host-supplied
`AuthorityContext`. Model-originated durable effects, unsafe adapter errors,
stale writes, and idempotency mismatches fail with safe typed values before
side effects.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-02 taxonomy, authority, idempotency, cancellation, and translation contracts in `specs/package-foundation/slices/PF-02-failures-authority.md`.
- README invariants for HUMAN/SERVICE/MODEL ownership and fail-closed input.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-02-failures-authority.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `study-domain-contract-worker`

Rationale:

The work is a provider-neutral value and error contract with strict domain
invariants, matching the existing profile and its safe-failure test gates.

## Context

Later durable commands need one public failure boundary and explicit caller
authority. Existing internal errors and adapter exceptions must remain private
while equal-key retries and stale writes are made replay-safe.

## Invariants

- The facade-visible failure set is exactly validation, stale, unauthorized, conflict, not found, unavailable dependency, and internal failure.
- Failures expose safe code, message, retryability, correlation ID, and structured details; credentials and raw tracebacks never serialize.
- Only an opaque context issued by the injected Host issuer and verified by its
  paired authority port can authorize HUMAN or SERVICE durable effects; MODEL
  is propose/read-only and cross-issuer contexts fail.
- Authority checks precede durable schema validation and adapter calls.
- Equal idempotency key plus equal canonical input converges; changed kind or bytes conflicts; stale input never mutates state; cancellation before append never appends.

## What To Do

- Implement the seven public failure classes, bounded strict-JSON safe
  serialization, and exhaustive internal/adapter translation.
- Implement the opaque, read-only, non-serializable Host issuer/context and
  paired authority-port capability plus immutable idempotency values.
- Reject MODEL durable effects before persistence/provider access and preserve local exception causes only for diagnostics.
- Add tests for all failure classes and legacy codes, bounded adversarial
  redaction, direct/replace/cross-issuer forgery, actor gates, retries, changed
  inputs, stale no-op, and cooperative cancellation.

## Likely Allowed Files / Packages

- `src/study_agent/api/authority.py`: public authority and failure exports.
- `src/study_agent/domain/errors.py`, `src/study_agent/application/errors.py`: failure values and translation.
- `src/study_agent/domain/authority.py`, `src/study_agent/ports/authority.py`: frozen authority/idempotency contracts.
- `tests/contract/test_public_failures.py`, `tests/contract/test_authority_context.py`, `tests/architecture/test_authority_boundaries.py`.

## Acceptance Criteria

- [ ] Exactly seven public failure subclasses inherit one facade-visible base.
- [ ] Every failure has bounded strict-JSON safe code/message/retryable/correlation/details and fully redacts credentials, cookies, prompts, chain-of-thought, and adapter tracebacks.
- [ ] Direct construction, replacement, assignment, serialization, cross-issuer contexts, and MODEL durable attempts fail before adapter access; issuer-matched HUMAN/SERVICE paths pass declared grants and scopes.
- [ ] Equal-key/equal-input calls return the prior result, changed bytes or command kind raise conflict, stale sequence is a no-op, and pre-commit cancellation has no event.
- [ ] Every legacy error enum plus provider, SQLite, filesystem, and unknown exceptions map explicitly to the closed taxonomy.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_failures.py tests/contract/test_authority_context.py tests/architecture/test_authority_boundaries.py`: taxonomy and authority tests pass.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_event_state_kernel.py tests/integration/test_capability_gateway_lifecycle.py`: existing durable paths remain green.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/api src/study_agent/domain src/study_agent/application tests/contract tests/architecture`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- New event envelopes, storage implementations, module registration, capability dispatch, runtime composition, package metadata, Cardine policy, browser credentials, auth, UI, or CLI.
- Retry scheduling, Job lifecycle, provider selection, and cross-user sharing.

## Removal Conditions

- Remove temporary public aliases for legacy error classes before closure.
- Keep private domain error codes only behind explicit facade mapping; no adapter exception may cross the boundary.
