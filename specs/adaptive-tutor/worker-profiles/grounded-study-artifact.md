# Worker Profile: grounded-study-artifact

## Mandate

Implement bounded, source-grounded study-artifact contracts and lifecycle
packages without redesigning tutor planning, provider adapters, or product UI.

## In Scope

- Strict artifact/profile values and codecs.
- Deterministic identity and immutable lineage.
- Source commitment and verified-run provenance.
- Event/reducer/service/view implementation under an approved bead.
- Prompt/validator packages for one explicitly named artifact capability.

## Forbidden Decisions

- Do not choose product workflow, next tutor action, learner-wide method, model,
  provider, deck, tags, Anki mutation, auth, billing, mastery, grading, or
  scheduling policy.
- Do not add public StudyTools, stores, global state, generic planner/DSL, or
  provider-specific behavior.
- Do not permit generated content to decide, accept, publish, or acquire
  authority.

## Required Context

- TUT-04 parent and assigned child bead.
- ADR-0002, ADR-0004, and ADR-0008.
- Existing study-context event/service/projection patterns.
- For flashcards, the versioned profile guidance in ADR-0008 and the assigned
  worker brief; personal skill examples are shape evidence, never factual data.

## Quality Gates

- Exact closed schemas and enums; unknown/extra fields fail closed.
- Canonical source commitments resolve and retain immutable revision identity.
- Provider/model selection policy and credentials are rejected from behavior and
  content contracts; observed adapter/model execution receipts remain required
  technical provenance.
- Idempotency, replay, authority, supersession, and deterministic bytes pinned.
- No change to the seven public StudyTools.

## Verification

- Narrow unit/contract checks first, then integration, Ruff, strict mypy, full
  offline pytest, and `git diff --check`.

## Report Format

- Outcome and files changed.
- Acceptance criteria satisfied.
- Exact commands/results.
- Risks, assumptions, or blocked contract decisions.
- Explicit statement that no forbidden file or behavior was changed.

## Reuse Trigger

Reuse for TUT-04 artifact/profile/lifecycle/capability beads and later bounded
artifact kinds that follow ADR-0008 without changing its architecture.
