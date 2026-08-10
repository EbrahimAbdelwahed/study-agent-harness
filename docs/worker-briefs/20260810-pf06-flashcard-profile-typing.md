# Worker Brief: PF-06 flashcard profile capability typing

## Assignment

Implement Bead `study-agent-harness-integration-1u7.1.3` tests-first. Narrow
validated morphology/hybrid capability identifiers without weakening canonical
construction or altering the gateway.

## Allowed files

- `src/study_agent/capabilities/morphology_flashcards.py`
- `src/study_agent/capabilities/hybrid_flashcards.py`
- `tests/unit/capabilities/test_morphology_flashcards.py`
- `tests/unit/capabilities/test_hybrid_flashcards.py`
- `tests/integration/test_headless_artifact_flow.py`

## Forbidden files and invariants

- Do not edit gateway, `test_flashcard_dispatch.py`, assessment/exam, public
  facade, source/citation, specs, package metadata, or reserved files.
- Do not add `Any`, blanket casts, ignores, or duplicate capability concepts.
- Preserve runtime behavior and canonical fingerprints unless a focused
  contract test proves an approved change.
- Do not delegate, merge, close beads, delete worktrees, or release another
  reservation. Commit only allowed files and report in the bead thread.

## Acceptance and verification

```text
uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/unit/capabilities/test_morphology_flashcards.py tests/unit/capabilities/test_hybrid_flashcards.py tests/integration/test_headless_artifact_flow.py
uv run --frozen --offline --python 3.13 --extra dev ruff check src/study_agent/capabilities/morphology_flashcards.py src/study_agent/capabilities/hybrid_flashcards.py tests/unit/capabilities/test_morphology_flashcards.py tests/unit/capabilities/test_hybrid_flashcards.py tests/integration/test_headless_artifact_flow.py
uv run --frozen --offline --python 3.13 --extra dev mypy --strict src/study_agent/capabilities/morphology_flashcards.py src/study_agent/capabilities/hybrid_flashcards.py tests/unit/capabilities/test_morphology_flashcards.py tests/unit/capabilities/test_hybrid_flashcards.py tests/integration/test_headless_artifact_flow.py
git diff --check
```

Report files, semantics, exact results, SHA, and blockers. Leave the bead open.
