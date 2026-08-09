# Task Bead: HR-07 Flashcard Job composition

Status: Open
Priority: P1
Type: task
Depends On: HR-05-lifecycle-convergence, HR-06-flashcard-planning, HR-04-decision-trace

## Outcome

Coordinator, leaf, independent reviewer, and assembler flashcard Jobs execute and recover through JobRuntime. ArtifactService remains the proposal/revision/decision owner; after exact parity and absence evidence, only the LessonWorker outer lifecycle is removed and release 1.2 is published through the shared RuntimeReleaseGate.

## Slice Strategy

migrate

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-07-flashcard-jobs.md`: handlers, independent review, partial proposals, exact LessonWorker removal inventory, parity/absence report, and release 1.2.
- `specs/future-runtime/README.md`: proposal-only output, no silent omission, one lifecycle, and release waves.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-07-flashcard-jobs.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a fixed Job composition and migration inventory with independent reviewer fixtures. Execute in one fresh Luna xhigh context.

## Context

HR-07 is the only LessonWorker removal bead. The exact current owner, symbols, and last consumers in HR-07 must be scanned. HR-05 generic lifecycle/playbook/GenerationWorker transitions remain governed by HR-05 and are not deleted here.

## What To Do

- Add coordinator/leaf/reviewer/assembler handlers behind `CapabilityExecutor`; keep reducers proposal-only and fetch source spans only for targeted conflicts.
- Add parity adapter and architecture absence report for every LessonWorker symbol/consumer named by HR-07.
- Remove only LessonWorker outer transitions, store, router, and bridge after parity; retain artifact services and HR-05 child receipts/proofs.
- Add release 1.2 evidence to the shared RuntimeReleaseGate.

## Likely Files / Packages

- `src/study_agent/flashcards/job_handlers.py`: coordinator, leaf, reviewer, assembler handlers.
- `src/study_agent/flashcards/**`: bounded reducer/parity adapters only.
- `src/study_agent/artifacts/**`: proposal-boundary extensions only.
- `tests/integration/test_flashcard_job_hierarchy.py`, `tests/integration/test_flashcard_partial_proposals.py`: Job recovery and visible partials.
- `tests/evals/test_hierarchical_flashcard_fixtures.py`: deterministic fixtures.
- `tests/architecture/test_flashcard_job_boundaries.py`: exact LessonWorker absence report.
- `tests/integration/test_headless_artifact_flow.py`: proposal/export regression.

## Acceptance Criteria

- [ ] All four handlers recover through JobRuntime; reviewer state is independent; reducers persist proposals/revisions/decisions only through ArtifactService.
- [ ] Missing clusters, failures, candidate conflicts, references, and coverage gaps remain visible; no silent omission or model auto-acceptance occurs.
- [ ] The exact HR-07 LessonWorker inventory is scanned; no Job handler writes LessonWorker statuses/checkpoints or owns `lesson_run_id`; generic HR-05 transitions are not removed here.
- [ ] After parity, only LessonWorker outer ownership is removed and no listed consumer imports the old service; artifact replay/export remains byte-stable.
- [ ] Focused test/absence gates and an independent semantic review gate both pass; the shared RuntimeReleaseGate publishes only release 1.2.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_flashcard_job_hierarchy.py tests/integration/test_flashcard_partial_proposals.py tests/evals/test_hierarchical_flashcard_fixtures.py tests/architecture/test_flashcard_job_boundaries.py tests/integration/test_headless_artifact_flow.py`: focused gates pass.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m mypy`: repository gates pass.
- `git diff --check`: clean.
- Clean wheel release gate: release 1.2 only.

## Out Of Scope

- Generic lifecycle/playbook/GenerationWorker removal, Cardine artifact policy, learner estimates, trace payloads in exports, model/provider dependencies, and edits outside listed paths.

## Invariants

- Artifact output stays proposal-only until an explicit authorized decision.
- HR-07 removes only LessonWorker outer ownership; HR-05 removals remain intact and are not repeated.
- Release 1.2 is emitted only by the shared gate after HR-07 evidence passes.

## Stop Conditions

- Stop before deletion if any tabled consumer lacks parity/restart proof or the absence report finds a dual writer.
- Stop if a reducer would accept model output or hide a failed cluster.

## Review Gate

Focused tests/absence and independent reviewer/semantic gates are separate prerequisites for release 1.2.

## Notes / Handoff

- HR-08, HR-09, HR-10, HR-11 remain independent branches after HR-05; HR-12 aggregates all releases.
