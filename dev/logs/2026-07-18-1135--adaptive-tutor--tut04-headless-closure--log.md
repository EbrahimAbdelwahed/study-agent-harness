# Log: TUT-04 headless closure

Date: 2026-07-18 11:35
Area: adaptive-tutor

## Summary

Closed TUT-04F and the TUT-04 parent milestone with a credential-free headless
lesson/exam story. The story uses the production verified-owner recovery graph,
canonical artifact lifecycle, human decisions/revision, replay/export, bounded
host-visible traces, and a deterministic typed eval report.

## Files Changed

- `tests/integration/test_headless_artifact_flow.py`: public lesson/exam paths,
  verified owner/proof recovery, lifecycle retries, process-loss reconstruction,
  redaction, evidence-handle, replay, and seven-tool gates.
- `tests/evals/test_headless_artifact_report.py`: canonical Export V2 report whose
  worker metrics derive from typed compact/review views.
- `specs/adaptive-tutor/beads/TUT-04F-headless-ui-readiness.md`: completed
  acceptance checklist.
- `specs/adaptive-tutor/beads/TUT-04-study-artifact-proposals.md`: parent closure.
- `specs/adaptive-tutor/beads/TUT-04C-grounded-flashcard-proposals.md`: child
  closure.
- `specs/adaptive-tutor/README.md`: durable milestone and next-lane summary.

## Verification

- `PYTHONPATH=.:src .venv/bin/python -m pytest -q`: 1558 passed, 2 skipped.
- `.venv/bin/ruff check src tests`: passed.
- `MYPYPATH=src .venv/bin/mypy --strict tests/integration/test_headless_artifact_flow.py tests/evals/test_headless_artifact_report.py`: passed.
- `MYPYPATH=src .venv/bin/mypy --strict src tests`: 120 pre-existing errors in
  14 older test files; neither new TUT-04F file reports an error.
- `uv build`: passed.
- Independent semantic review: no remaining findings.

## Notes

- The generic dialogue suspend/resume lifecycle remains covered by
  `tests/integration/test_optional_dialogue_lifecycle.py`; the TUT-04F story pins
  and verifies the hybrid playbook's no-clarification skip branch.
- No production API, provider SDK, dependency, StudyTool, or `sbobby-web` change
  was introduced.
