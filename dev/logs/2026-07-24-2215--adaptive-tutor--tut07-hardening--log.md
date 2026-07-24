# Log: TUT-07 hardening

Date: 2026-07-24 22:15
Area: adaptive-tutor / recall

## Summary

Applied the approved TUT-07A/B/C hardening findings without changing event
bytes, schema versions, provider dependencies, or TUT-07D composition.

## Files Changed

- `src/study_agent/recall/projection.py`: recompute review identity and reject
  opaque or malformed projected records.
- `src/study_agent/recall/service.py`: remove session-batch coupling, resolve
  effective retry policies, and use one typed recall-view constructor order.
- `src/study_agent/recall/due.py`: derive artifact and recall state from one
  loaded projection high-water mark.
- `src/study_agent/recall/events.py`, `view.py`, and `ports/recall.py`: strict
  review-id decoding, projection allowlists, and public command-port typing.
- `.github/workflows/ci.yml`: add Python 3.12/3.13 optional-FSRS and clean-wheel
  recall smoke coverage while preserving the base wheel job.
- `tests/`: forged identity, longitudinal session, retry policy, exact shape,
  strict decoding, due high-water, and structural typing regressions.

## Verification

- `python -m pytest tests/integration/test_recall_service.py tests/unit/recall tests/contract/recall tests/architecture/test_recall_port_typing.py`: 33 passed.
- `python -m pytest tests/architecture/test_recall_boundaries.py tests/unit/adapters/scheduling/test_py_fsrs.py`: 4 passed, 8 skipped because optional `fsrs` is not installed locally.
- `python -m ruff check ...`: passed.
- `.../.venv/bin/python -m mypy src tests/...`: passed.
- `git diff --check`: passed.

## Notes

- The FSRS tests are intentionally skipped in this base environment; the new
  CI recall job installs `.[dev,recall]` and runs the clean-wheel smoke.
