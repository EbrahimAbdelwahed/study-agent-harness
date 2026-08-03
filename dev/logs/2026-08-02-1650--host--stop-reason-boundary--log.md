# Log: Stop reason boundary

Date: 2026-08-02 16:50 CEST
Area: host

## Summary

Removed the ambiguous learner-input member from the shared `TutorStopReason`
contract. `StopDecision` now supports only `completed` and `no_safe_action`.
The generated structured-output schema inherits that exact inventory, and the
strict decoder rejects the legacy serialized reason with `ValueError` rather
than mapping it to a runner outcome.

`AskLearnerDecision` remains the only learner-question decision and still
returns `TutorHostRunStatus.NEEDS_LEARNER_INPUT`. The runner behavior for
completed and no-safe-action stops is unchanged. No manifests or maintained
public documentation contained the removed stop reason; the remaining text in
the runner and historical worker brief describes the valid ask-result status.

## Files Changed

- `src/study_agent/hosts/contracts.py`: remove the legacy stop enum member.
- `tests/unit/hosts/test_tutor_host_contracts.py`: pin the exact schema,
  supported round trips, and strict legacy decode rejection.
- `tests/unit/hosts/test_tutor_host_runner.py`: pin ask and both supported stop
  flows.
- `dev/plans/2026-08-02-1648--host--stop-reason-boundary--plan.md`: scoped plan.

## Verification

- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/hosts/test_tutor_host_contracts.py tests/unit/hosts/test_tutor_host_runner.py`:
  41 passed.
- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/hosts tests/unit/adapters/host/test_openai_responses.py`:
  60 passed.
- `.venv/bin/python -m ruff check src/study_agent/hosts/contracts.py tests/unit/hosts/test_tutor_host_contracts.py tests/unit/hosts/test_tutor_host_runner.py`:
  passed.
- `.venv/bin/python -m mypy src/study_agent/hosts/contracts.py src/study_agent/hosts/runner.py tests/unit/hosts/test_tutor_host_contracts.py tests/unit/hosts/test_tutor_host_runner.py`:
  passed, four files checked.
- `git diff --check`: passed.

## Notes

- No runner, tool-operation, manifest, downstream product, network, or release
  behavior was changed.
- The five pre-existing untracked files remain unmodified and excluded.
