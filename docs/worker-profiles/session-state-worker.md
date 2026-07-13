# Worker Profile: session-state-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch6/session-event-kernel.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `session-event-kernel Implement typed event-sourced session state`.

## Mandate

Complete recurring work shaped like `session-event-kernel` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch6/session-event-kernel.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/domain/{identifiers,session,provenance,grounding}.py`: stable session/answer/provenance entities
- `src/study_agent/ports/session.py`: projection-only session view
- `src/study_agent/sessions/{events,projection,summary,view}.py`: codecs/reducers/summary/view
- relevant package `__init__.py` exports
- `tests/unit/sessions/` and `tests/contract/session/`: strict state and view contracts

May inspect:

- `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch6/session-event-kernel.md`
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
-   - All session payloads and envelopes are strictly decoded before reduction.
-   - Reducers preserve unrelated source state and reject duplicate/cross-session/stale/terminal writes.
-   - Insufficient answers represent model provenance as absent rather than fabricated.
-   - Continuation summaries are deterministic, bounded, linked to canonical history, and never replace interactions.
-   - Session views expose immutable projection data without storage-specific types.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/sessions tests/contract/session`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/domain src/study_agent/ports/session.py src/study_agent/sessions tests/unit/sessions tests/contract/session`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/domain src/study_agent/ports/session.py src/study_agent/sessions tests/unit/sessions tests/contract/session`: expected to pass or produce documented output
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
