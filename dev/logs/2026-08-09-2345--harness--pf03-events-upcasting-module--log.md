# Log: PF-03 events, upcasting, and module

Date: 2026-08-09 23:45
Area: Harness package foundation

## Summary

Converged PF-03 on one canonical SQLite event store and replay path. The
curated `EventEnvelope` now normalizes typed/string IDs, preserves optional
session lineage, rejects malformed or naive timestamps, and serializes as
canonical JSON. Transitional `DomainEvent` input remains private to state
reducers and retains its historical bytes. `EventRegistry.prepare` resolves a
declared current schema and performs adjacent upcasting before decode/reduce.

The removed `api.events`, `EnvelopeEventStore`, and `replay_envelopes` seams are
not available. Storage/runtime facades expose the approved event/module
symbols, and the manifest adds only `event_envelope: 1` to schema versions.

## Files Changed

- `src/study_agent/domain/events.py`: shared event-type validation, envelope
  normalization/codec, and legacy validation.
- `src/study_agent/events/upcasting.py`: deterministic adjacent upcasters for
  envelope and transitional legacy events.
- `src/study_agent/state/{registry,projection,serialization}.py`: preparation,
  mixed replay, and dual codec support.
- `src/study_agent/adapters/sqlite/event_store.py`: one-table mixed append/read,
  original-byte retention, full-batch preparation, and rebuild replay.
- `src/study_agent/kernel/module.py`, `src/study_agent/ports/storage.py`:
  shared validator and one event-store protocol.
- `src/study_agent/api/{storage,runtime,manifest}.py`: curated lazy facade
  symbols and envelope schema manifest.
- `tests/contract/events/**`, `tests/integration/test_event_state_kernel.py`,
  `tests/contract/test_public_manifest.py`, and
  `tests/architecture/test_public_facade_boundaries.py`: PF-03 coverage.
- `specs/package-foundation/README.md`: PF-03 evidence/checklist update.

## Verification

- `.venv/bin/python -m pytest -q tests/contract/events tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py tests/architecture/test_import_boundaries.py tests/architecture/test_capability_gateway_boundaries.py`: 27 passed.
- `.venv/bin/python -m pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py tests/contract/test_public_manifest_import_safety.py`: 10 passed.
- `.venv/bin/ruff check ...` (PF-03 source/tests scope): passed.
- `.venv/bin/mypy ...` (PF-03 source scope): passed.
- `uv run --python 3.13 ...`: blocked by sandbox access to the shared uv cache; equivalent `.venv` checks passed.

## Notes

- PF-03 bead remains open for orchestrator review; no PF-04 or later behavior
  was added.
