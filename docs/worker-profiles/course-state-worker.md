# Worker Profile: course-state-worker

Generated: 2026-07-12
Source task: `docs/tasks/20260712-oss-harness-v01-batch7/course-profile-kernel.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `course-profile-kernel Implement immutable canonical course profiles`.

## Mandate

Complete recurring work shaped like `course-profile-kernel` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-typed-tools-and-reference-harness.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch7/course-profile-kernel.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- domain/course.py and course exports
- new courses/events.py, projection.py, service.py, view.py
- ports/course.py
- ingestion/service.py and sessions/service.py guards
- course unit/contract/integration tests

May inspect:

- `docs/specs/oss-harness-v0-1-typed-tools-and-reference-harness.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260712-oss-harness-v01-batch7/course-profile-kernel.md`
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
-   - Same profile is idempotent; changed profile conflicts.
-   - Envelope/profile/course identity and exact payload are strict.
-   - Orphan ingestion/session start fails before blobs/events.
-   - Mixed replay remains byte-identical.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/courses tests/contract/course tests/integration/test_course_profile_kernel.py`: expected to pass or produce documented output
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
