# Worker Profile: cli-release-test-worker

Generated: 2026-07-12
Source task: `docs/tasks/20260712-oss-harness-v01-batch8/reference-cli-release-gates.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `reference-cli-release-gates Prove offline CLI flow, packaging, docs, and release behavior`.

## Mandate

Complete recurring work shaped like `reference-cli-release-gates` without redesigning the feature.

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
- `docs/tasks/20260712-oss-harness-v01-batch8/reference-cli-release-gates.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- tests/integration/test_reference_cli.py
- README.md
- docs/examples
- packaging/CI files

May inspect:

- `<spec path>`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch8/reference-cli-release-gates.md`
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
-   - The approved end-to-end journey passes without network or keys.
-   - Installed study-agent works on Python 3.12.
-   - Public docs explain external-agent integration and honest cancellation/index recovery semantics.

## Verification

Run:

```bash
`.venv/bin/python -m pytest`: expected to pass or produce documented output
`.venv/bin/python -m ruff check .`: expected to pass or produce documented output
`.venv/bin/python -m mypy`: expected to pass or produce documented output
`clean Python 3.12 build/install/CLI smoke`: expected to pass or produce documented output
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
