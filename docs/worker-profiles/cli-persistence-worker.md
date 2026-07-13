# Worker Profile: cli-persistence-worker

Generated: 2026-07-12
Source task: `docs/tasks/20260712-oss-harness-v01-batch8/cli-persistence-prerequisites.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `cli-persistence-prerequisites Add durable run state, system clock, and catalog reads`.

## Mandate

Complete recurring work shaped like `cli-persistence-prerequisites` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `<spec path>`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch8/cli-persistence-prerequisites.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- src/study_agent/adapters/sqlite/run_store.py and adapter exports
- src/study_agent/adapters/system/clock.py and exports
- minimal session/course read-port and projection-view changes
- focused contract and unit tests

May inspect:

- `<spec path>`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch8/cli-persistence-prerequisites.md`
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
-   - Run state survives reopening and CAS conflicts cannot overwrite newer checkpoints.
-   - SystemClock always returns aware UTC datetimes.
-   - Catalog reads are deterministic, course-isolated, projection-only, and empty-safe.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/test_run_store_contract.py tests/contract/session tests/unit/adapters/system`: expected to pass or produce documented output
`.venv/bin/python -m pytest`: expected to pass or produce documented output
`.venv/bin/python -m ruff check .`: expected to pass or produce documented output
`.venv/bin/python -m mypy`: expected to pass or produce documented output
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
