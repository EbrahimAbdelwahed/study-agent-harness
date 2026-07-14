# Worker Brief: TUT-01 production

## Goal

Implement the production contract in
`specs/adaptive-tutor/beads/TUT-01-progressive-study-context.md` using the
`adaptive-study-state-worker` profile.

## Allowed Files

- `src/study_agent/domain/study_context.py`
- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/study_context/**`
- `src/study_agent/ports/study_context.py`
- `src/study_agent/ports/__init__.py`
- `src/study_agent/cli/repository.py` only for event registration/composition
- `src/study_agent/adapters/sqlite/lifecycle_observer.py` only for event
  registration/composition
- `src/study_agent/application/export.py` only for strict context-event
  allowlisting/validation

## Forbidden Files

- all tests;
- tools, skills, playbooks, prompts, lifecycle, model adapters, README, and
  files outside the allowed list.

## Fixed Invariants

- Closed kinds and scalar/additive cardinality are fixed by slice 01.
- Originating session and interaction identities are mandatory.
- No recency-based conflict resolution.
- HUMAN/SERVICE only; expected-sequence CAS and deterministic retry identity.
- Require the idempotency key. Resolve an exact committed retry before stale
  sequence rejection; reject changed content under the same command identity.
- Origin interaction must exist, be HUMAN, and belong to the envelope session.
- Do not add CLI commands or change StudyTools.

## Acceptance

Production code imports cleanly, composes through the existing event registry,
and supports the full bead contract for an independent test worker.

## Verification

- `.venv/bin/ruff check` on changed production files
- `.venv/bin/mypy --strict src`
- existing course/session/context-adjacent tests if available
- `git diff --check`
