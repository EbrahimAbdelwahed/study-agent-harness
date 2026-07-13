# Task Bead: session-event-kernel Implement typed event-sourced session state

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch6`
Spec: `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`

## Worker Profile

create `session-state-worker`

Rationale:

No reusable specialization selected yet.

## Context

Persistent sessions need strict canonical events, pure reducers, bounded derived context, and projection-only views before answer finalization can safely write state.

## What To Do

- Refine session, answer, identifier, and provenance domain contracts, including optional model provenance for deterministic insufficient results.
- Implement exact-key session lifecycle/interaction/answer/summary event codecs with complete envelope validation.
- Implement pure mixed-stream reducers and registry composition preserving source projection state.
- Implement deterministic bounded continuation summary generation and validation.
- Define SessionViewPort and a projection-backed reference reader without mutation or SQLite leakage.

## Likely Files / Packages

- `src/study_agent/domain/{identifiers,session,provenance,grounding}.py`: stable session/answer/provenance entities
- `src/study_agent/ports/session.py`: projection-only session view
- `src/study_agent/sessions/{events,projection,summary,view}.py`: codecs/reducers/summary/view
- relevant package `__init__.py` exports
- `tests/unit/sessions/` and `tests/contract/session/`: strict state and view contracts

## Acceptance Criteria

- [ ] All session payloads and envelopes are strictly decoded before reduction.
- [ ] Reducers preserve unrelated source state and reject duplicate/cross-session/stale/terminal writes.
- [ ] Insufficient answers represent model provenance as absent rather than fabricated.
- [ ] Continuation summaries are deterministic, bounded, linked to canonical history, and never replace interactions.
- [ ] Session views expose immutable projection data without storage-specific types.

## Verification

- `.venv/bin/python -m pytest tests/unit/sessions tests/contract/session`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/domain src/study_agent/ports/session.py src/study_agent/sessions tests/unit/sessions tests/contract/session`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/domain src/study_agent/ports/session.py src/study_agent/sessions tests/unit/sessions tests/contract/session`: expected to pass or produce documented output

## Out Of Scope

- Run recovery, application finalization, public tools, CLI/export, providers, and product work.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
