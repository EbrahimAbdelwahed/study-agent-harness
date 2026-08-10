# Log: PF-04 storage contract kit

Date: 2026-08-10 00:00
Area: Harness package foundation

## Summary

Implemented the PF-04 provider-neutral storage seam and reusable offline
contract kit. The canonical PF-03 envelope remains the only event bytes; event
idempotency is persisted as a command-boundary record. Memory, SQLite, and
filesystem adapters now share typed stale/conflict/not-found/integrity outcomes,
and run storage remains operational CAS state rather than canonical learner
state. The Terra follow-up publishes the canonical six-port facade, requires
keys on public envelope writes, and routes existing production DomainEvent
writers through a private legacy seam.

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
- `src/study_agent/adapters/sqlite/namespaced_run_store.py`
- `src/study_agent/adapters/filesystem/blob_store.py`
- `src/study_agent/{artifacts,assessments,courses,ingestion,recall,sessions,study_context}/**`
- `src/study_agent/playbooks/engine.py`
- `tests/architecture/test_public_facade_boundaries.py`
- `tests/contract/event_store/test_sqlite_event_store.py`
- `tests/contract/run_store/test_sqlite_run_store.py`
- `tests/contract/source_content/test_source_content_contract.py`
- `tests/contract/storage/test_storage_contract_kit.py`
- `tests/integration/test_event_state_kernel.py`
- `tests/integration/test_substrate_production.py`
- `tests/integration/test_text_ingestion.py`
- `docs/worker-reports/20260809-harness-package-foundation/pf-04.md`

## Verification

- Python 3.12 contract/integration/Ruff/mypy gates passed (63 tests; 559
  mypy files).
- Python 3.13 contract/integration/Ruff/mypy gates passed (63 tests; 559
  mypy files).
- Full offline suite: 2361 passed, 15 skipped, one unrelated TCP browser
  bind failure caused by the sandbox.

## Notes

- Public `storage.__all__`/`dir()` now publish all six ports and typed
  outcomes; `EventStore` is the canonical `ports.storage.EventStore` object.
- Production event writers use `_append_legacy`; only keyed envelope writes
  use the public append contract. Existing test doubles and fixtures were
  migrated to the optional blob ref parameter or keyed/private seams.
- `study-agent-harness-integration-pf-04-wnl` is intentionally left open for
  orchestrator review.
