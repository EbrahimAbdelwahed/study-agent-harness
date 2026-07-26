# Log: KB-01 canonical substrate

Date: 2026-07-26 22:52
Area: knowledge-base

## Summary

Completed the first canonical-evidence increment for KB v0.2. The harness now
has provider-neutral frozen text substrates, source-bound production receipts,
strict event decoding, deterministic projections, and automatic migration of
persisted v0.1 source projections without rewriting canonical events.

## Files Changed

- `src/study_agent/domain/identifiers.py`: domain-separated substrate and production identities with strict page-map validation.
- `src/study_agent/domain/substrate.py`: immutable substrate, pagination, and production contracts.
- `src/study_agent/ingestion/substrate.py`: service-authorized, idempotent production boundary.
- `src/study_agent/ingestion/substrate_events.py`: strict canonical event codec and blob verification.
- `src/study_agent/ingestion/substrate_projection.py`: bytes-only substrate and production projections.
- `src/study_agent/ingestion/projection.py`: v0.1 compatibility reducer and lazy projection migration.
- `src/study_agent/state/registry.py`: deterministic projection-migration hook.
- `src/study_agent/adapters/sqlite/event_store.py`: lazy migration on projection load, persisted only for writable stores.
- `tests/`: independent identity, authority, corruption, replay, migration, and architecture coverage.

## Verification

- `.venv/bin/python -m pytest -q`: 1820 passed, 11 skipped.
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: success across 471 source files.
- `git diff --check`: passed.
- Independent semantic review: all original and follow-up findings resolved.

## Notes

- No model, provider, network, OCR, vector, UI, or tutor dependency was added.
- The next dependency-ready beads are KB-02 and KB-04.
