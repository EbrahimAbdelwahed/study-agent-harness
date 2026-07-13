# Worker Profile: session-finalization-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch6/session-answer-finalizer.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `session-answer-finalizer Finalize verified grounded runs into sessions atomically`.

## Mandate

Complete recurring work shaped like `session-answer-finalizer` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch6/session-answer-finalizer.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/sessions/{service,provenance}.py`: application finalization
- `src/study_agent/skills/builtin/grounded_answer.py`: exact allowed state writes
- narrow application/reference orchestration module if required
- `tests/unit/sessions/test_service.py`, `tests/integration/test_session_answer_replay.py`, `tests/integration/test_session_continuity.py`, and eval/architecture coverage

May inspect:

- `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch6/session-answer-finalizer.md`
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
-   - Only verified validated results persist; failed/tampered runs never append domain events.
-   - One exchange is one atomic event batch and retrying it never duplicates events.
-   - Every supported answer has exact source/prompt/model/retrieval/validator/run provenance; insufficient has no invented model call.
-   - Resume uses only bounded continuation summary and preserves canonical history/replay equivalence.
-   - No commit ToolStep, public tool manifest, provider logic, or product scope is introduced.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/sessions/test_service.py tests/integration/test_session_answer_replay.py tests/integration/test_session_continuity.py tests/architecture`: expected to pass or produce documented output
`.venv/bin/python -m pytest`: expected to pass or produce documented output
`.venv/bin/python -m ruff check .`: expected to pass or produce documented output
`.venv/bin/python -m mypy`: expected to pass or produce documented output
`git diff --check`: expected to pass or produce documented output
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
