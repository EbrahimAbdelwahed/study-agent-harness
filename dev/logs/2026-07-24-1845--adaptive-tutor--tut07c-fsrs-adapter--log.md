# Log: TUT-07C optional py-fsrs adapter

Date: 2026-07-24 18:45 CEST
Area: adaptive-tutor / recall scheduling

## Summary

Implemented the exact-pinned optional `fsrs==6.3.1` adapter. The adapter is
lazy and fail-closed, explicitly configures all FSRS scheduler parameters with
fuzzing disabled, reconstructs a fresh card from ordered provider-neutral
history, maps all four ratings, normalizes UTC, and returns only
`SchedulingResult`. No FSRS object or package state enters canonical events or
DTOs.

The conformance pass exposed that the former core-only policy fingerprint could
not attest adapter-effective parameters. Added the generic,
domain-separated `effective_policy_fingerprint` helper and wired it through
`SchedulingResult`, `AppliedSchedule`, and replay validation without changing
the event field shape. Fake scheduler fixtures now use the same helper.

## Preflight evidence

- Python 3.12 and 3.13 disposable environments: `fsrs==6.3.1` installed with
  `uv`; metadata reports MIT License and `Requires-Python >=3.10`.
- Public API smoke: `Scheduler`, `Card`, `Rating`, `State`, and `ReviewLog`; the
  API documents `review_duration` as milliseconds, matching `latency_ms`.
- The package's 21 published model parameters were copied into the adapter's
  descriptor and passed explicitly; retention, learning/relearning steps,
  maximum interval, and `enable_fuzzing=False` are explicit too.

## Files changed

- `src/study_agent/adapters/scheduling/`: optional adapter and exports.
- `src/study_agent/recall/contracts.py`: effective policy fingerprint helper
  and strict receipt validation.
- `src/study_agent/recall/projection.py`: replay validation uses the helper.
- `src/study_agent/recall/__init__.py`: public helper export.
- `pyproject.toml`: exact `recall = ["fsrs==6.3.1"]` extra only.
- `tests/unit/adapters/scheduling/`, `tests/contract/recall/`,
  `tests/unit/recall/`, `tests/integration/test_recall_service.py`, and
  `tests/architecture/`: golden, negative, conformance, boundary, and fake
  fixture coverage.

## Verification

- `pytest` focused recall + adapter + architecture: **37 passed** with the
  exact optional package available.
- Base-only focused adapter import: **4 passed, 8 skipped**; base import does
  not load `fsrs`, and composition returns an actionable `FsrsUnavailableError`.
- Ruff focused source/tests: **passed**.
- Strict mypy focused source/adapter tests: **passed**. Broader test mypy
  still reports pre-existing untyped fixture errors outside this package.
- `git diff --check`: **passed**.
- `uv build`: base wheel and sdist built. Wheel metadata contains
  `Provides-Extra: recall` and `Requires-Dist: fsrs==6.3.1; extra == "recall"`.
- Clean base wheel import without FSRS: **passed**. Clean `[recall]` wheel
  install with exact FSRS on Python 3.12: **passed**. Python 3.13 API/license
  smoke: **passed**.

## Remaining

- Parent integration branch must cherry-pick this checkpoint and run its
  aggregate/full-suite gates. TUT-07D remains dependent on this adapter.
