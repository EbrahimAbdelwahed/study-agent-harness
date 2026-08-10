# Worker Brief: PF-06 assessment and exam capability typing

## Assignment

Implement Bead `study-agent-harness-integration-1u7.1.2` tests-first. Narrow
validated capability identifiers at the assessment/exam boundary without
weakening canonical constructors.

## Allowed files

- `src/study_agent/assessments/verified_grading.py`
- `src/study_agent/exams/analysis.py`
- `tests/unit/assessments/test_verified_grading.py`
- `tests/unit/exams/test_exam_analysis.py`

## Forbidden files and invariants

- Do not edit gateway, flashcard capability, public facade, source/citation,
  specs, package metadata, or another worker's tests.
- Do not add `Any`, blanket casts, ignores, or a duplicate capability concept.
- Preserve runtime failure behavior and provider-neutral contracts.
- Do not delegate, merge, close beads, delete worktrees, or release another
  reservation. Commit only allowed files and report in the bead thread.

## Acceptance and verification

Add behavior-oriented regressions if the narrowing is not already pinned, then
run:

```text
uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/unit/assessments/test_verified_grading.py tests/unit/exams/test_exam_analysis.py
uv run --frozen --offline --python 3.13 --extra dev ruff check src/study_agent/assessments/verified_grading.py src/study_agent/exams/analysis.py tests/unit/assessments/test_verified_grading.py tests/unit/exams/test_exam_analysis.py
uv run --frozen --offline --python 3.13 --extra dev mypy --strict src/study_agent/assessments/verified_grading.py src/study_agent/exams/analysis.py tests/unit/assessments/test_verified_grading.py tests/unit/exams/test_exam_analysis.py
git diff --check
```

Report files, semantics, exact results, SHA, and blockers. Leave the bead open.
