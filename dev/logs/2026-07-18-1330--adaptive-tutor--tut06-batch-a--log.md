# Log: TUT-06 Batch A

Date: 2026-07-18 13:30
Area: adaptive-tutor

## Summary

Completed TUT-06B and TUT-06C. The harness now has a bounded,
provider-neutral tutor runner with durable exact continuations and a trusted
host boundary for immutable local text/Markdown snapshots and explicit source
ingestion.

The implementation preserves canonical event ownership: the runner and file
registry write no course events, and only the explicit trusted ingestion bridge
may call the existing ingestion service. Model-visible contracts contain no
continuation authority, local paths, file bytes, source trust, or provider
configuration.

## Files Changed

- `src/study_agent/hosts/runner.py`: bounded decisions, retries, stale refresh,
  interruption, continuation codecs, and typed outcomes.
- `src/study_agent/hosts/files.py`: strict host file values, canonical codec,
  registry, lookup, expiry, and ingestion bridge.
- `src/study_agent/ports/tutor_runner.py`: narrow runner authority/effect ports.
- `src/study_agent/ports/host_file.py`: narrow file identity/store/ingestion
  ports.
- `src/study_agent/adapters/memory/host_file.py`: atomic bounded operational
  snapshot store and deterministic trusted identity adapter.
- `src/study_agent/capabilities/contracts.py` and `gateway.py`: exact frozen
  suspended dialogue response schema.
- Focused unit, contract, integration, and architecture tests for both beads.

## Review

- Aggregated reviewer found retry-budget coupling, an invalid stop mapping,
  expired snapshot reuse, malformed-payload accounting bypass, incomplete
  result/codec validation, non-atomic memory limits, and redundant aliases.
- All findings were fixed; targeted re-review result: APPROVE.
- `HostRetryReceipt` is deliberately strict v2 because legacy receipts cannot
  prove host-turn or decision-generation binding.

## Verification

- `PYTHONPATH=.:src .venv/bin/python -m pytest -q`: 1612 passed, 2 skipped.
- `.venv/bin/ruff check src tests`: passed.
- `MYPYPATH=src .venv/bin/mypy --strict src`: passed, 222 files.
- `uv build`: built sdist and wheel.
- `git diff --check`: passed.

## Notes

- Expected skips: sandbox Unix-socket fixture and opt-in network model smoke.
- TUT-06C supports `.txt` and `.md` only; renewal/eviction, PDF/OCR/audio, UI,
  provider adapters, and automatic ingestion remain out of scope.
