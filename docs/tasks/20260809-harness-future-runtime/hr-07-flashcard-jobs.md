# Task Bead: hr-07-flashcard-jobs Flashcard Job composition

Status: Open
Priority: P1
Type: task
Depends On: hr-05-lifecycle-convergence, hr-06-flashcard-planning, hr-04-decision-trace
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Coordinator, leaf, independent reviewer, and assembler flashcard Jobs execute through JobRuntime; proposals remain ArtifactService-owned; only LessonWorker outer ownership is removed after parity and release 1.2 is gated.

## Slice Strategy

migrate

Fresh Context Fit: yes

## Spec Coverage

- HR-07 handlers, independent review, partial proposals, exact LessonWorker removal inventory, parity/absence, and release 1.2.
- README proposal-only output, no omission, one lifecycle, and release waves.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-07-flashcard-jobs.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Fixed Job composition and LessonWorker inventory fit one fresh Luna xhigh context.

## Context

HR-07 is the only LessonWorker removal bead; HR-05 generic transitions are not removed here.

## What To Do

- Add handlers and proposal-boundary adapters.
- Add exact LessonWorker symbol/consumer absence report and restart parity.
- Remove only LessonWorker outer transitions/store/router/bridge after proof; emit 1.2 evidence.

## Likely Files / Packages

- src/study_agent/flashcards/job_handlers.py
- src/study_agent/flashcards/**
- src/study_agent/artifacts/**
- tests/integration/test_flashcard_job_hierarchy.py
- tests/integration/test_flashcard_partial_proposals.py
- tests/evals/test_hierarchical_flashcard_fixtures.py
- tests/architecture/test_flashcard_job_boundaries.py
- tests/integration/test_headless_artifact_flow.py

## Acceptance Criteria

- [ ] All handlers recover through JobRuntime; reviewer is independent; ArtifactService remains proposal/revision/decision owner.
- [ ] Missing/failure/conflict/coverage entries remain visible; no auto-acceptance or silent omission.
- [ ] Exact LessonWorker inventory passes, only LessonWorker outer ownership is removed, and separate test/absence, semantic/reviewer, and release gates publish 1.2.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_flashcard_job_hierarchy.py tests/integration/test_flashcard_partial_proposals.py tests/evals/test_hierarchical_flashcard_fixtures.py tests/architecture/test_flashcard_job_boundaries.py tests/integration/test_headless_artifact_flow.py`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output
- `Clean wheel release gate: 1.2 only`: expected to pass or produce documented output

## Out Of Scope

- Generic lifecycle/playbook/GenerationWorker removal, Cardine policy, learner estimates, trace exports, provider dependencies, and paths outside HR-07.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
