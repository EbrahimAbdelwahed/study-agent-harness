# Worker Profile: citation-resolution-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch4/source-content-resolver.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `source-content-resolver Implement event-backed canonical source and citation resolution`.

## Mandate

Complete recurring work shaped like `source-content-resolver` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch4/source-content-resolver.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/retrieval/content.py`: event-backed content/catalog adapter
- `src/study_agent/retrieval/errors.py`: structured resolution errors
- `src/study_agent/retrieval/__init__.py`: explicit public surface
- `tests/contract/source_content/`: source-content/citation behavior
- `tests/integration/test_source_content_resolution.py`: ingestion-to-resolution proof

May inspect:

- `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch4/source-content-resolver.md`
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
-   - Exact normalized text is returned only after blob/event validation.
-   - Every resolved citation lies inside its declared immutable chunk and returns canonical text.
-   - Wrong ownership, offsets, quote, missing revision, and corruption fail explicitly.
-   - Current/superseded revision document metadata is deterministic and event-derived.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/retrieval tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/retrieval tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output
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
