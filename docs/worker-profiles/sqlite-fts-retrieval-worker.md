# Worker Profile: sqlite-fts-retrieval-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch4/fts-retrieval.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `fts-retrieval Implement portable SQLite FTS5 lexical retrieval`.

## Mandate

Complete recurring work shaped like `fts-retrieval` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch4/fts-retrieval.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/ports/retrieval.py`: portable document/query/result refinements
- `src/study_agent/adapters/sqlite/fts_retrieval.py`: derived lexical index
- `src/study_agent/adapters/sqlite/__init__.py`: explicit adapter export
- `tests/contract/retrieval/`: reusable retrieval behavior
- `tests/integration/test_fts_retrieval.py`: ingestion/index/search/citation/rebuild flow
- `tests/evals/test_lexical_retrieval_fixtures.py`: expected source/chunk fixtures

May inspect:

- `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch4/fts-retrieval.md`
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
-   - Search applies course/revision/kind/role/trust/current filters before limiting.
-   - Literal query compilation prevents FTS syntax/control injection.
-   - Every result resolves to canonical text and exact citation; row IDs never escape.
-   - Ordering is deterministic and index rebuild preserves equivalent public results.
-   - No candidates returns insufficient; candidates returns sufficient; conflicting is not fabricated.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals/test_lexical_retrieval_fixtures.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/ports/retrieval.py src/study_agent/adapters/sqlite/fts_retrieval.py tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/ports/retrieval.py src/study_agent/adapters/sqlite/fts_retrieval.py tests/contract/retrieval tests/integration/test_fts_retrieval.py tests/evals`: expected to pass or produce documented output
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
