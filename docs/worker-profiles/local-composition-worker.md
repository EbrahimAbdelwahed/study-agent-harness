# Worker Profile: local-composition-worker

Generated: 2026-07-12
Source task: `docs/tasks/20260712-oss-harness-v01-batch8/local-repository-composition.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `local-repository-composition Compose a strict non-secret local repository`.

## Mandate

Complete recurring work shaped like `local-repository-composition` without redesigning the feature.

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
- `docs/tasks/20260712-oss-harness-v01-batch8/local-repository-composition.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- src/study_agent/cli/repository.py
- src/study_agent/cli/config.py
- focused unit/integration tests

May inspect:

- `<spec path>`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch8/local-repository-composition.md`
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
-   - No credential value is persisted.
-   - No provider/model branch enters domain, ports, prompts, skills, or playbooks.
-   - Repository initialization is offline, idempotent, and rejects incompatible collisions.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/cli`: expected to pass or produce documented output
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
