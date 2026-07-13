# Worker Profile: content-addressed-storage-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01-batch2/local-content-store.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `local-content-store Implement immutable filesystem content-addressed storage`.

## Mandate

Complete recurring work shaped like `local-content-store` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01-batch2/local-content-store.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/adapters/filesystem/`: filesystem BlobStore implementation and errors
- `tests/contract/blob_store/`: reusable BlobStore behavior tests
- `tests/integration/test_filesystem_blob_store.py`: corruption, idempotency, and path-safety tests

May inspect:

- `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01-batch2/local-content-store.md`
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
-   - Repeated puts of identical bytes return the same BlobRef and one immutable object.
-   - Get verifies checksum and length and reports missing/corrupt content explicitly.
-   - All object paths remain within the configured root and malformed references cannot traverse or follow attacker-controlled symlinks.
-   - Publication is atomic and cannot replace different bytes at a digest path.
-   - No dependency or provider/runtime type is introduced.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/adapters/filesystem tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/adapters/filesystem tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output
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
