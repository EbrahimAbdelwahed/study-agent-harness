# Log: PF-04 storage contract kit

Date: 2026-08-10 00:00
Area: Harness package foundation

## Summary

Implemented the PF-04 provider-neutral storage seam and reusable offline
contract kit. The canonical PF-03 envelope remains the only event bytes; event
idempotency is persisted as a command-boundary record. Memory, SQLite, and
filesystem adapters now share typed stale/conflict/not-found/integrity outcomes,
and run storage remains operational CAS state rather than canonical learner
state.

## Files changed

- `src/study_agent/api/storage.py`
- `src/study_agent/ports/storage.py`
- `src/study_agent/ports/clock.py`
- `src/study_agent/ports/id_factory.py`
- `src/study_agent/ports/__init__.py`
- `src/study_agent/adapters/memory/storage.py`
- `src/study_agent/adapters/memory/__init__.py`
- `src/study_agent/adapters/sqlite/event_store.py`
- `src/study_agent/adapters/sqlite/run_store.py`
- `src/study_agent/adapters/filesystem/blob_store.py`
- `tests/contract/storage/test_storage_contract_kit.py`
- `docs/worker-reports/20260809-harness-package-foundation/pf-04.md`

## Verification

- Python 3.12 contract/integration/Ruff/mypy gates passed.
- Python 3.13 contract/integration/Ruff/mypy gates passed.
- Full offline suite: 2357 passed, 15 skipped, one unrelated TCP browser
  bind failure caused by the sandbox.

## Notes

- PF-03 public `storage.__all__` and `dir()` remain unchanged for existing
  import-safety tests; new PF-04 ports are lazy direct imports from the same
  facade.
- `study-agent-harness-integration-pf-04-wnl` is intentionally left open for
  orchestrator review.
