# Worker Profile: python-oss-bootstrap-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01/harness-repo-bootstrap.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `harness-repo-bootstrap Bootstrap the isolated Python OSS package`.

## Mandate

Complete recurring work shaped like `harness-repo-bootstrap` without redesigning the feature.

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
- `docs/tasks/20260710-oss-harness-v01/harness-repo-bootstrap.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `pyproject.toml`: package metadata and development tooling
- `README.md`: contributor-oriented project boundary and commands
- `src/study_agent/`: package skeleton only
- `tests/architecture/`: import-boundary checks
- `.gitignore`: local Python artifacts

May inspect:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/harness-repo-bootstrap.md`
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
-   - A clean Python 3.12 environment can install the distribution.
-   - The package imports with no provider SDK, Tau, web framework, or retrieval framework installed.
-   - Formatting, typing, unit-test, and architecture commands are documented and runnable.
-   - No Sbobby or existing workspace application is imported or modified.

## Verification

Run:

```bash
`python3 -m pytest`: expected to pass or produce documented output
`python3 -m mypy src`: expected to pass or produce documented output
`python3 -m ruff check .`: expected to pass or produce documented output
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
