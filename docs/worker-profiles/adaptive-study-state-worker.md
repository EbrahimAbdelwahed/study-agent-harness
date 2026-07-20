# Worker Profile: adaptive-study-state-worker

Generated: 2026-07-14
Source task: `specs/adaptive-tutor/beads/TUT-01-progressive-study-context.md`

## Reuse Trigger

Use for bounded event-sourced adaptive-tutor state owners whose contracts,
events, conflict rules, and projection shape are already fixed.

## Mandate

Implement one strict course-scoped state owner through domain values, event
codecs, reducer, projection view, application service, and repository
composition without redesigning the feature.

## Scope

In scope:

- strict immutable values and schema-versioned event codecs;
- deterministic identities, expected-sequence CAS, retries, and safe errors;
- pure reducers and projection-backed views;
- package exports and explicitly named composition points.

Out of scope:

- product or architecture decisions;
- prompt behavior, model/provider integrations, UI, or autonomous planning;
- new dependencies, generic persistence abstractions, or unrelated refactors.

## Required Context

Read first:

- `specs/adaptive-tutor/README.md`
- relevant slice and bead
- `docs/decisions/ADR-0002--event-state-skills-playbooks.md`
- `docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md`
- existing course, ingestion, and session event/service patterns
- applicable `AGENTS.md`

Current-doc research: not needed.

## Allowed Files

The worker brief must list exact domain/package/port/composition files. Do not
edit tests when a separate test worker owns them.

## Forbidden Decisions

Stop and report before deciding:

- new statement kinds or cardinality rules;
- canonical versus derived state changes;
- compatibility or migration policy;
- public StudyTool changes;
- provider, runtime, or UI choices.

## Quality Gates

- Exact event envelopes and payload keys are validated.
- MODEL actors cannot acquire canonical write authority.
- Commands are deterministic, idempotent, CAS-safe, and course-owned.
- Reducers are pure and mixed replay remains deterministic.
- Errors do not expose content or persistence internals.
- Existing event owners and seven StudyTools remain unchanged.

## Verification

Run focused tests supplied by the bead, then full pytest, Ruff, strict mypy,
and `git diff --check`. Report any pre-existing failure separately.

## Report Format

Return files changed, behavior, exact verification, constraints followed,
unresolved questions, and recommended review step.
