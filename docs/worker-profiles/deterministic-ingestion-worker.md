# Worker Profile: deterministic-ingestion-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch3/text-markdown-ingestion.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `text-markdown-ingestion Implement deterministic text and Markdown ingestion`.

## Mandate

Complete recurring work shaped like `text-markdown-ingestion` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch3/text-markdown-ingestion.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/ingestion/normalization.py`: canonical UTF-8 normalization
- `src/study_agent/ingestion/chunking.py`: deterministic spans and identifiers
- `src/study_agent/ingestion/service.py`: application orchestration and structured results/errors
- `src/study_agent/ingestion/__init__.py`: explicit public surface
- `tests/unit/ingestion/`: normalization/chunking/id tests
- `tests/integration/test_text_ingestion.py`: CAS/event/replay/idempotency integration

May inspect:

- `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch3/text-markdown-ingestion.md`
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
-   - Original and normalized bytes are immutable and checksummed.
-   - Every chunk span resolves exactly and deterministically into normalized text.
-   - Identical ingestion appends no duplicate event; changed bytes create a new revision.
-   - Invalid UTF-8/extension and sequence conflicts are explicit structured failures.
-   - No model, retrieval, provider, or direct projection mutation is introduced.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/ingestion tests/integration/test_text_ingestion.py tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/ingestion tests/unit/ingestion tests/integration/test_text_ingestion.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/ingestion tests/unit/ingestion tests/integration/test_text_ingestion.py`: expected to pass or produce documented output
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
