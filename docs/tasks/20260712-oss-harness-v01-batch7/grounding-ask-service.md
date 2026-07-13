# Task Bead: grounding-ask-service Implement the canonical grounded ask use case

Status: Open
Priority: P1
Type: task
Depends On: course-profile-kernel
Run ID: `20260712-oss-harness-v01-batch7`
Spec: `docs/specs/oss-harness-v0-1-typed-tools-and-reference-harness.md`

## Worker Profile

create `grounding-ask-worker`

Rationale:

No reusable specialization selected yet.

## Context

Direct, tool and harness surfaces need one crash-safe ordinary use case.

## What To Do

- Implement request-scoped internal context/search executors using trusted context and canonical course/session/source services.
- Derive deterministic run identity/pins/read dependencies and explicit duplicate-run state handling.
- Execute or safely recover the grounded playbook, then finalize through GroundedSessionFinalizer.
- Return canonical AnswerRecord plus coarse validated service events.

## Likely Files / Packages

- application/grounding_ask.py and application contracts/exports
- tools/playbook_bridge.py if needed
- narrow built-in flow binding adjustments
- unit/integration ask/recovery tests

## Acceptance Criteria

- [ ] One use case owns execute/recover/finalize.
- [ ] No authority/provider/prompt/pin selection comes from generated arguments.
- [ ] Retries never repeat external effects; changed requests conflict.
- [ ] All persisted results remain canonical and fully provenanced.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_grounding_ask_service.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- Public tool registry, CLI/export, token streaming, generic agents.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
