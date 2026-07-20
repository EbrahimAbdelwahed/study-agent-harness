# Handoff: Build Week submission finalization

Date: 2026-07-20 11:48 CEST
Area: release / demo / submission

## Current State

Study Agent Harness 0.2.0 alpha has a judge-ready installed anatomy demo,
Build Week README copy, Devpost copy, and a 2:43 avatar-free video package. The
official HeyGen Remote MCP is configured, but OAuth/account-credit verification
is waiting for the user to return to the computer. No render, upload, or
submission has been authorized or performed.

## Completed

- TUT-06E clean-wheel gate reconfirmed with the final wheel.
- Added `study-agent-demo` with a bundled sanitized anatomy fixture, human trace,
  and inspectable JSON trace.
- Added the installed demo smoke to CI.
- Prepared Devpost fields, judge instructions, voiceover/caption master, shot
  list, recording plan, thumbnail concept, and HeyGen brief.
- Preserved the two unrelated untracked duplicate Markdown files.

## Remaining

- Complete official HeyGen OAuth, inspect account/remaining credits through MCP,
  and present the exact render proposal before spending credits.
- Record the six real project clips and obtain explicit approval before any paid
  render, YouTube upload, Devpost modification, or submission.
- Fill the public YouTube URL and Codex `/feedback` Session ID.

## Important Context

- The public release wording is `0.2.0 alpha`.
- The full configured mypy gate on mypy 2.3.0 still reports the previously known
  120 errors in 14 test-fixture files. The distributed `src/` tree and all demo
  and adversarial-eval files are strict-mypy clean; this submission pass did not
  widen scope to unrelated fixture typing debt.

## Verification

- `.venv/bin/python -m pytest`: 1664 passed, 3 skipped.
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy src`: 233 source files passed.
- `.venv/bin/python -m mypy src/study_agent/demo tests/integration/test_reference_tutor_host_demo.py tests/evals/test_reference_tutor_host_adversarial.py`: passed.
- `uv build`: sdist and wheel built successfully.
- Clean Python 3.12 wheel install: OpenAI SDK absent; human and JSON
  `study-agent-demo` smoke tests passed.
- `git diff --check`: passed.
