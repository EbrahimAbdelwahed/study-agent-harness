# Task Bead: AML-03 explicit lifecycle and retry

Status: Complete
Priority: P1
Type: task
Depends On: AML-01

## Worker Profile

reuse `implementer`

Rationale:

The course/session services already own the required behavior. This bead is a
bounded CLI registry and handler exposure with recovery-focused tests.

## Context

Automation cannot currently list courses, explicitly create a stable first
session, or read back that session identity before a retry-safe ask.

## What To Do

- Register deterministic `course list`.
- Register idempotent `session start COURSE --session-id ID`.
- Register read-only `session get COURSE SESSION`.
- Preserve legacy automatic-session ask while marking it convenience-only in
  discovery metadata.
- Add lifecycle, cross-course identity, restart, and stable-ask retry coverage.

## Likely Files / Packages

- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/commands.py`
- `tests/contract/cli/test_explicit_lifecycle.py`

## Acceptance Criteria

- [x] Course list is deterministic for empty and populated repositories.
- [x] Repeating session start for the same course/session is a noop.
- [x] The same session text under another course is a distinct identity.
- [x] Session get returns stable status/identity without mutation.
- [x] Stable session/key ask retry produces one canonical answer/model effect.
- [x] Changed question under the same key conflicts safely.
- [x] Legacy automatic-session ask remains compatible.

## Verification

- `python -m pytest tests/contract/cli/test_explicit_lifecycle.py tests/integration/test_reference_cli_release.py`
- `python -m pytest`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`

## Out Of Scope

- Tool composition from AML-02, operator-skill packaging, manifest lifecycle,
  new StudyTools, or authority from model arguments.

## Notes / Handoff

- Session authority is the host-supplied `(course_id, session_id)` pair.
- Retryable session-start races have a distinct machine-clean
  `retryable_conflict` envelope; deterministic conflicts remain non-retryable.
