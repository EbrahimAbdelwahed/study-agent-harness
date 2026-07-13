# Task Bead: session-answer-finalizer Finalize verified grounded runs into sessions atomically

Status: Open
Priority: P1
Type: task
Depends On: session-event-kernel, trusted-run-receipts
Run ID: `20260711-oss-harness-v01-batch6`
Spec: `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`

## Worker Profile

create `session-finalization-worker`

Rationale:

No reusable specialization selected yet.

## Context

The event kernel and trusted operational receipts must be joined by an application service that commits validated exchanges exactly once and resumes from bounded context without making ToolStep effects crash-unsafe.

## What To Do

- Implement lifecycle commands and projection-backed session context reads under trusted ExecutionContext ownership.
- Assemble canonical GroundedAnswer and complete provenance only from verified run, evidence, traces, pins, registry versions, and citation resolution.
- Atomically append question, answer/assistant interaction, and summary events with deterministic identities and idempotency fingerprints.
- Handle same-key retries, changed-payload conflicts, sequence races, failures, insufficient no-model results, and terminal sessions explicitly.
- Prove crash-after-run recovery, suspend/resume bounded prompt context, mixed source/session replay, projection rebuild, and StateWritePolicy enforcement.

## Likely Files / Packages

- `src/study_agent/sessions/{service,provenance}.py`: application finalization
- `src/study_agent/skills/builtin/grounded_answer.py`: exact allowed state writes
- narrow application/reference orchestration module if required
- `tests/unit/sessions/test_service.py`, `tests/integration/test_session_answer_replay.py`, `tests/integration/test_session_continuity.py`, and eval/architecture coverage

## Acceptance Criteria

- [ ] Only verified validated results persist; failed/tampered runs never append domain events.
- [ ] One exchange is one atomic event batch and retrying it never duplicates events.
- [ ] Every supported answer has exact source/prompt/model/retrieval/validator/run provenance; insufficient has no invented model call.
- [ ] Resume uses only bounded continuation summary and preserves canonical history/replay equivalence.
- [ ] No commit ToolStep, public tool manifest, provider logic, or product scope is introduced.

## Verification

- `.venv/bin/python -m pytest tests/unit/sessions/test_service.py tests/integration/test_session_answer_replay.py tests/integration/test_session_continuity.py tests/architecture`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Public typed tools, CLI/export, model-authored summary, live network tests, semantic entailment, and product scope.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
