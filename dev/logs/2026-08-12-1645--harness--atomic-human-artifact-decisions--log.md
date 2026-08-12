# Log: Atomic HUMAN artifact bulk decisions

Date: 2026-08-12 16:45
Area: Harness PF-07 artifacts

## Summary

Implemented the approved atomic HUMAN artifact decision contract. The service
prevalidates a bounded ordered manifest, rejects duplicate revisions or
duplicate artifact lineages, creates only existing v1
`study_artifact.decision_recorded` events, and appends the complete event batch
once. Bulk retry identities are deterministic from the host bulk key, ordinal,
and manifest digest; receipts are reconstructed from canonical event history,
so no new event payload fields, schema, database table, store, or outbox was
introduced.

## Files Changed

- `src/study_agent/artifacts/contracts.py`: typed request, result, and receipt.
- `src/study_agent/artifacts/events.py`: manifest/request and child retry
  fingerprint helpers.
- `src/study_agent/artifacts/service.py`: HUMAN bulk command, prevalidation,
  one-batch append, retry/conflict detection, and receipt reconstruction.
- `src/study_agent/ports/artifact.py`, `src/study_agent/api/artifacts.py`,
  `src/study_agent/artifacts/__init__.py`: typed public exports.
- `tests/unit/artifacts/test_lifecycle_service.py`: mixed outcome, zero-write,
  duplicate-lineage, retry, and manifest-conflict coverage.
- `tests/integration/test_artifact_bulk_decisions.py`: SQLite batch/restart and
  invalid-last atomicity coverage.

## Verification

- `.venv/bin/pytest -q tests/unit/artifacts tests/integration/test_artifact_bulk_decisions.py tests/integration/test_artifact_repository_replay.py tests/integration/test_recall_ledger_replay.py tests/integration/test_recall_service.py`: **167 passed**.
- `.venv/bin/ruff check ...`: **pass**.
- `.venv/bin/mypy ...`: **pass**, 25 source files.
- `git diff --check`: **pass**.

## Constraints

- No Cardine, recall/assessment behavior, database schema, new event type,
  provider/UI, dependency, or unrelated coordination file was modified.
- Existing single-item decisions and replay remain covered by the prior suite.

## Follow-up

- Independent semantic review should inspect event-history retry recovery,
  cross-session identity collision handling, and the no-intra-batch-dependency
  rule before integration.
