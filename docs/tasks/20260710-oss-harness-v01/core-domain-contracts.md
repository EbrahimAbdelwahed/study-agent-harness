# Task Bead: core-domain-contracts Implement immutable domain and public port contracts

Status: Completed
Priority: P1
Type: task
Depends On: harness-repo-bootstrap
Run ID: `20260710-oss-harness-v01`
Spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Worker Profile

create `study-domain-contract-worker`

Rationale:

No reusable specialization selected yet.

## Context

The event kernel, skills, playbooks, retrieval, and adapters require provider-free value objects and protocols with stable epistemic and provenance vocabulary.

## What To Do

- Implement immutable identifiers, course, source revision, chunk, citation, session, grounded-answer, provenance, event-envelope, error, execution-context, model, retrieval, blob, clock, and run contracts required by the approved spec.
- Validate invariants at construction boundaries without embedding persistence or provider behavior.
- Expose a deliberately small documented public surface and add behavior-focused tests.

## Likely Files / Packages

- `src/study_agent/domain/`: immutable entities, value objects, events, provenance, and errors
- `src/study_agent/ports/`: framework-neutral protocols and request/result types
- `tests/unit/domain/`: domain invariant tests
- `tests/contract/`: public contract and provider-independence tests

## Acceptance Criteria

- [x] Domain and port contracts contain no provider, Tau, SQLite, CLI, or web types.
- [x] Canonical mutations can be represented as versioned DomainEvent envelopes with course sequence, actor, causation, correlation, and clock metadata.
- [x] Course, immutable source revision, stable citation span, session, and grounded-answer invariants are enforced.
- [x] ModelPort exposes canonical messages, structured-output constraints, capabilities, usage, cancellation, and streaming vocabulary without study prompts or policy.

## Verification

- `python3 -m pytest tests/unit/domain tests/contract`: expected to pass or produce documented output
- `python3 -m mypy src/study_agent/domain src/study_agent/ports`: expected to pass or produce documented output
- `python3 -m ruff check src/study_agent/domain src/study_agent/ports tests/unit/domain tests/contract`: expected to pass or produce documented output

## Out Of Scope

- SQLite implementations, event reducers, skill behavior, prompt content, provider adapters, and application orchestration.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
