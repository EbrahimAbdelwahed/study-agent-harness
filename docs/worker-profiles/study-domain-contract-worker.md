# Worker Profile: study-domain-contract-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01/core-domain-contracts.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `core-domain-contracts Implement immutable domain and public port contracts`.

## Mandate

Complete recurring work shaped like `core-domain-contracts` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/core-domain-contracts.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/domain/`: immutable entities, value objects, events, provenance, and errors
- `src/study_agent/ports/`: framework-neutral protocols and request/result types
- `tests/unit/domain/`: domain invariant tests
- `tests/contract/`: public contract and provider-independence tests

May inspect:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/core-domain-contracts.md`
- applicable `AGENTS.md` files

Do not edit:

- Files outside the bead's approved scope.
- Files reserved by another active worker.

## Forbidden Decisions

Stop and report back before deciding:

- architecture boundaries outside the task bead
- product behavior not covered by acceptance criteria
- new dependencies or provider choices
- data model or persistence changes not specified by the orchestrator

## Quality Gates

- Change stays within the task file/package scope.
- Acceptance criteria are implemented or explicitly reported as blocked.
- Verification commands from the task bead are run or a concrete reason is reported.
- Acceptance criteria from the bead remain the source of truth:
-   - Domain and port contracts contain no provider, Tau, SQLite, CLI, or web types.
-   - Canonical mutations can be represented as versioned DomainEvent envelopes with course sequence, actor, causation, correlation, and clock metadata.
-   - Course, immutable source revision, stable citation span, session, and grounded-answer invariants are enforced.
-   - ModelPort exposes canonical messages, structured-output constraints, capabilities, usage, cancellation, and streaming vocabulary without study prompts or policy.

## Verification

Run:

```bash
`python3 -m pytest tests/unit/domain tests/contract`: expected to pass or produce documented output
`python3 -m mypy src/study_agent/domain src/study_agent/ports`: expected to pass or produce documented output
`python3 -m ruff check src/study_agent/domain src/study_agent/ports tests/unit/domain tests/contract`: expected to pass or produce documented output
```

If verification cannot run, report the reason and the narrowest manual check completed.

## Report Format

Return:

- files changed;
- behavior implemented;
- verification results;
- profile constraints followed;
- unresolved questions;
- recommended next worker or review step.
