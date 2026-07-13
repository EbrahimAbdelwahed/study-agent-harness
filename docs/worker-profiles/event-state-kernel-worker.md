# Worker Profile: event-state-kernel-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01/event-state-kernel.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `event-state-kernel Implement the event-sourced SQLite state kernel`.

## Mandate

Complete recurring work shaped like `event-state-kernel` without redesigning the feature.

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
- `docs/tasks/20260710-oss-harness-v01/event-state-kernel.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/state/`: registry, reducers, projection state, canonical serialization, replay
- `src/study_agent/adapters/sqlite/`: SQLite event and projection adapter
- `tests/unit/state/`: reducer and serialization tests
- `tests/contract/event_store/`: event-store conformance tests
- `tests/integration/`: atomic append, conflict, rebuild, and replay tests

May inspect:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/event-state-kernel.md`
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
-   - Canonical mutations append typed events; projection tables have no public direct-write path.
-   - Event append and synchronous projection update commit or roll back together.
-   - Per-course sequence conflicts fail explicitly without partial mutation.
-   - Deleting projections and replaying the same event/reducer versions yields byte-identical canonical serialized state.
-   - Reducer code is deterministic and side-effect-free.

## Verification

Run:

```bash
`python3 -m pytest tests/unit/state tests/contract/event_store tests/integration`: expected to pass or produce documented output
`python3 -m mypy src/study_agent/state src/study_agent/adapters/sqlite`: expected to pass or produce documented output
`python3 -m ruff check src/study_agent/state src/study_agent/adapters/sqlite tests/unit/state tests/contract/event_store tests/integration`: expected to pass or produce documented output
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
