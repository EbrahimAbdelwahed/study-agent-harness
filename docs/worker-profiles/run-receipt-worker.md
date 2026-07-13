# Worker Profile: run-receipt-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch6/trusted-run-receipts.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `trusted-run-receipts Expose trusted retrieval, validator, and recovered-run receipts`.

## Mandate

Complete recurring work shaped like `trusted-run-receipts` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch6/trusted-run-receipts.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/ports/retrieval.py`, retrieval envelope, and SQLite FTS adapter: provider-neutral receipts
- `src/study_agent/playbooks/{contracts,runtime,engine}.py`: validator trace details and verified recovery
- relevant package exports
- `tests/contract/retrieval`, `tests/unit/playbooks`, and `tests/integration/test_playbook_engine.py`: receipt/recovery coverage

May inspect:

- `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch6/trusted-run-receipts.md`
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
-   - Retrieval provenance is explicit and never hardcoded by session/application code.
-   - Validator identities/outcomes come from registered executors and canonical result fingerprints.
-   - Recovered results are immutable, fully verified, and never rerun external steps.
-   - Only completed or semantically successful deterministic termination is recoverable for finalization.
-   - Existing retrieval and playbook behavior remains provider-neutral and offline.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/ports/retrieval.py src/study_agent/retrieval src/study_agent/adapters/sqlite/fts_retrieval.py src/study_agent/playbooks tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/ports/retrieval.py src/study_agent/retrieval src/study_agent/adapters/sqlite/fts_retrieval.py src/study_agent/playbooks tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
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
