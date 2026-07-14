# Task Bead: TUT-01 progressive study context

Status: Ready
Priority: P0
Type: tracer-bullet
Depends On: none

## Worker Profile

create and reuse `adaptive-study-state-worker`; use `test-engineer` for
independent contract coverage after production contracts are fixed

## Context

`CourseProfile` is immutable and complete, while `session.record_note` is
opaque. An adaptive tutor needs typed, progressively collected learner
statements without mutating course identity or promoting model inference to
truth.

## What To Do

- Add strict domain values for the closed statement vocabulary.
- Add statement-recorded, statement-retracted, and conflict-resolved codecs.
- Add pure reducers and a projection-backed context view.
- Add a service with trusted actor checks, course ownership, expected-sequence
  CAS, deterministic idempotency, and explicit scalar conflict resolution.
- Register the events in local repository and lifecycle-observer composition,
  and extend export-v1's event allowlist, without adding CLI or StudyTool
  commands.
- Add unit, contract, mixed-replay, race, and integration coverage.

## Likely Files / Packages

- `src/study_agent/domain/study_context.py`
- `src/study_agent/domain/identifiers.py`
- `src/study_agent/study_context/`
- `src/study_agent/ports/study_context.py`
- package exports, local/lifecycle event-registry composition, and export-v1
  strict validation
- `tests/unit/study_context/`, `tests/contract/study_context/`
- `tests/integration/test_progressive_study_context.py`

## Acceptance Criteria

- [ ] Missing study context is a valid empty view for an existing course.
- [ ] Each statement requires an originating session and interaction identity.
- [ ] The origin is an existing HUMAN interaction in the same course/session.
- [ ] MODEL actors and orphan courses fail before an append.
- [ ] Scalar contradictions are visible and not resolved by recency.
- [ ] Explicit resolution selects an existing active statement and retains history.
- [ ] Resolution supersedes losers; later conflicts reopen; winner retraction
  does not resurrect losers.
- [ ] Retry with identical identity and content is idempotent; changed content conflicts.
- [ ] Stale expected sequence returns a retryable conflict without mutation.
- [ ] Mixed course/source/session/context replay is byte-identical.
- [ ] Lifecycle observation and export-v1 remain compatible after context events.
- [ ] Existing v0.2 behavior and seven StudyTool fingerprints remain unchanged.
- [ ] CourseProfile values remain attributed setup hints and are never silently
  converted into, or preferred over, learner statements.
- [ ] `study_context` is covered by the core import-boundary architecture gate.

## Verification

- `.venv/bin/python -m pytest -q tests/unit/study_context tests/contract/study_context tests/integration/test_progressive_study_context.py`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/ruff check .`
- `.venv/bin/mypy --strict src tests`
- `git diff --check`

## Out Of Scope

- General tutor turns, tutor snapshot, agent choice, capability gateway,
  artifacts, assessment, recall, UI, provider calls, and `sbobby-web`.

## Grilling Evidence

Approved decisions are recorded in the spec README and ADR-0004. No new ADR or
glossary decision is delegated to this bead.
