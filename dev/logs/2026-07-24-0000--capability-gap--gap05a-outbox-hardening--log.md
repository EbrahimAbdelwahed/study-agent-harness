# Log: GAP-05A outbox hardening

Date: 2026-07-24 00:00
Area: capability-gap feedback

## Summary

Applied the two approved P1 findings. Export now claims one deterministic batch
atomically, publishes only post-PENDING bytes, and finalizes with a compare-and-
swap against exact aggregate payloads. Concurrent observations or resolutions
remain pending for a later export; exact report retries remain idempotent.
The portable schema is version 2 and emits only closed dimensions, contract
identity fingerprints, and a harness fingerprint; raw identities and harness
versions are not representable in outbox bytes.

## Files Changed

- `src/study_agent/feedback/outbox.py`: strict redacted dimensions, v2 bundle,
  portable key binding, CAS-bound export coordinator.
- `src/study_agent/adapters/sqlite/capability_gap_store.py`: atomic claim and
  CAS finalize operations; requeue on new observations/resolutions after export.
- `src/study_agent/ports/capability_gap.py`: claim/finalize storage contract.
- `tests/unit/feedback/test_capability_gap_outbox.py`: redaction, idempotency,
  restart, barrier/concurrency and CAS regression coverage.

## Verification

- `pytest -q tests/unit/feedback tests/integration/test_capability_gap_sqlite.py tests/architecture/test_capability_gap_boundaries.py`: 40 passed.
- `ruff check` on changed source/tests: passed.
- `mypy` on changed source: passed.
- `pytest -q tests/architecture`: 84 passed.
- `git diff --check`: passed.

## Notes

- No dependencies, network, Flywheel/devkit, provider adapters, or canonical
  course events were changed.
- Hosted transport and downstream GAP-05B/C/D remain separate beads.
