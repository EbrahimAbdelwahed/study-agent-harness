# Worker Profile: source-state-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch3/source-revision-state.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `source-revision-state Implement typed source-revision events and replayable projections`.

## Mandate

Complete recurring work shaped like `source-revision-state` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch3/source-revision-state.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/domain/source.py`: normalized content/revision contract additions
- `src/study_agent/ingestion/events.py`: typed ingestion event payload and decoder
- `src/study_agent/ingestion/projection.py`: source reducer registration and projection helpers
- `tests/unit/ingestion/`: payload and reducer tests
- `tests/integration/test_source_projection_replay.py`: SQLite replay proof

May inspect:

- `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch3/source-revision-state.md`
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
-   - Malformed source/chunk payloads fail before event insertion.
-   - A valid ingestion event rebuilds byte-identical source/chunk projection state.
-   - Earlier revisions remain present when a later revision is reduced.
-   - No provider, retrieval, model, or direct projection-write behavior is introduced.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/domain/source.py src/study_agent/ingestion tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/domain/source.py src/study_agent/ingestion tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
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
