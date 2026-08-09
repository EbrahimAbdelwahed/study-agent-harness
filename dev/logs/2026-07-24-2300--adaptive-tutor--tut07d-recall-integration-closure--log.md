# Log: TUT-07D recall integration closure

Date: 2026-07-24 23:00 CEST
Area: adaptive-tutor / recall integration

## Summary

Added optional recall composition to repository and lifecycle observation, a
strict v3 public export with one `recall.jsonl` receipt stream, and exact
fail-closed v1/v2 behavior for recall-bearing streams. The recall CI job now
executes the real FSRS lifecycle test on Python 3.12 and 3.13; the test also
rebuilds projection and reopens without a scheduler to prove replay does not
invoke FSRS.

## Files Changed

- `src/study_agent/recall/composition.py`: typed optional scheduler/factory
  composition and safe availability result.
- `src/study_agent/recall/__init__.py`: public composition exports.
- `src/study_agent/cli/repository.py`: additive recall registration and
  mutually-exclusive optional scheduler composition.
- `src/study_agent/adapters/sqlite/lifecycle_observer.py`: additive recall
  registration for read-only lifecycle replay.
- `src/study_agent/application/export.py`: v3 bundle, replay, strict receipt
  allowlist, and legacy fail-closed checks.
- `src/study_agent/adapters/filesystem/export.py`: atomic v3 writer with
  `recall.jsonl`, leaving v1/v2 layouts untouched.
- `src/study_agent/application/__init__.py`, `src/study_agent/cli/registry.py`:
  public v3 constants and CLI version 3.
- `.github/workflows/ci.yml`: explicit real-FSRS E2E and recall architecture
  checks in both supported Python versions.
- `tests/integration/test_recall_composition.py`,
  `tests/contract/export/test_recall_export_v3.py`,
  `tests/integration/test_recall_real_fsrs_e2e.py`: focused regressions.

## Verification

- `python -m pytest` focused recall/export/composition suite: 44 passed, 1
  skipped locally because `fsrs==6.3.1` is not installed in the base venv.
- `ruff check` focused changed Python files: passed.
- `/study-agent-harness/.venv/bin/mypy --strict src`: passed.
- `git diff --check`: passed.
- Independent review found and the integration pass fixed two issues:
  v1 now prioritizes the exact recall-v3 error when artifact and recall events
  coexist, and invalid scheduler/factory results fail at composition rather
  than on the first command.
- Integration also made the new composition exports lazy to preserve clean
  imports through the provider-neutral ports package.
- Full repository suite after those fixes: 1,754 passed, 11 skipped (only
  optional/network tests); Ruff, strict mypy, and `git diff --check`: passed.
- The first remote matrix run exposed two CI-only gaps: tests imported lazy
  composition exports in a way mypy 3.13 could not type, and the real-FSRS
  fixture used a timestamp older than the repository's system-clock session
  event. Both fixtures were corrected without weakening either gate; full
  configured mypy now checks all 461 source and test files successfully.
- GitHub Actions run `30113999281`: all Python 3.12/3.13 base and recall jobs
  passed, including real FSRS E2E, clean-wheel installation, CLI smoke, Ruff,
  and full configured mypy.

## Notes

- The real FSRS test is intentionally optional locally but is not omitted from
  the recall CI job, which installs the exact extra first.
- The console-script `pytest` entry point needs `PYTHONPATH=.` in this
  sandbox; CI uses `python -m pytest`, which resolves the repository test
  package normally.
- No provider package, Anki field, mutable schedule, or event-store write is
  owned by export or canonical recall modules.
