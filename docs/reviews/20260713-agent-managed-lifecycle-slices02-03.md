# Review Report: Agent-managed lifecycle slices 02–03

Date: 2026-07-13
Reviewer: code-quality-governor

## Findings

- [P2, closed] `src/study_agent/cli/main.py`: retryable session-start races
  initially fell through to generic `operational_failure`; they now emit the
  stable `retryable_conflict` envelope before the RuntimeError fallback.
- [P2, closed] `src/study_agent/tools/builtin.py`: callable inference made eager
  service versus lazy provider ambiguous. A nominal provider now owns explicit
  `resolve()` and successful-resolution memoization.

## Required Fixes

- None remaining.

## Test Gaps

- First provider resolution is not synchronized across threads. Concurrent
  construction is outside slice 02; canonical/model-effect idempotency remains
  enforced by the existing run and event contracts.
- Live provider smoke remains opt-in.

## Verification Commands

- `python -m pytest -q`: passed, 434 tests; one opt-in network smoke skipped.
- `python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 164 source files.
- `git diff --check`: passed.

## Architecture Notes

- Exact-seven StudyTool manifests and fingerprints are unchanged.
- Registry enumeration does not rebuild retrieval or resolve a model; only
  `grounding.ask` resolves the nominal lazy provider.
- Missing-model ask writes no run or domain event and returns the portable
  `incompatible_runtime` tool error.
- Course/session lifecycle delegates to canonical projections and
  `SessionService`; no lifecycle command became a StudyTool.
- An architecture guard forbids reverse imports from application/domain/ports/
  tools into CLI composition.

## Prompt / Eval Notes

- No prompts, model policy, skills, playbooks, RAG behavior, or eval fixtures changed.

## Verdict

Approved after closing both P2 findings.
