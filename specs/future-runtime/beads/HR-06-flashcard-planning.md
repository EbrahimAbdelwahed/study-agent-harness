# Task Bead: HR-06 Hierarchical flashcard work plans

Status: Open
Priority: P1
Type: task
Depends On: HR-01-contract-firewall, HR-03-executor-recovery, HR-05-lifecycle-convergence

## Outcome

Flashcard coordinator/leaf work plans are deterministic, bounded, and explicit about partial coverage. Every leaf has one evidence cluster, at most six candidates, a declared context budget, stable child identity, and visible missing-cluster/failure entries.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-06-flashcard-planning.md`: plan contracts, stable child identity, context/candidate limits, and partial coverage.
- `specs/future-runtime/README.md`: opaque source refs, no silent omission, and bounded hierarchy.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-06-flashcard-planning.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a deterministic planner/contracts pass with golden vectors and no model or persistence behavior. Execute in one fresh Luna xhigh context.

## Context

HR-06 supplies plans for HR-07 Job handlers. Existing flashcards planning can remain an adapter, but it cannot create a competing child identity or omit failed clusters.

## What To Do

- Add `FlashcardWorkPlan`, `EvidenceClusterRef`, `LeafTask`, `CandidateLimit`, and `PartialCoverage` plus `plan_flashcard_jobs`.
- Preserve opaque source/citation refs; enforce one cluster per leaf, six-candidate cap, context budget, depth 1, and 64-child limits.
- Compute stable child identity from parent, position, and task fingerprint using HR-01/03 contracts.
- Add deterministic vectors and adversarial budget/omission fixtures.

## Likely Files / Packages

- `src/study_agent/flashcards/jobs.py`: plan and task contracts.
- `src/study_agent/flashcards/planner.py`: deterministic planning and child identity.
- `tests/unit/flashcards/test_job_planning.py`: planner behavior.
- `tests/contract/flashcards/test_work_plan_vectors.py`: canonical vectors.
- `tests/adversarial/test_flashcard_context_budget.py`: caps, depth, and partial semantics.

## Acceptance Criteria

- [ ] Equal inputs produce byte-identical plans and child fingerprints; changed task bytes conflict.
- [ ] Every leaf carries one opaque evidence cluster, no more than six candidates, and a validated context budget.
- [ ] Every missing cluster or failure is represented in `PartialCoverage`; no silent omission or automatic acceptance is possible.
- [ ] Focused planner test gate passes; an independent semantic review confirms no Cardine policy or competing child identity.

## Verification

- `.venv/bin/python -m pytest tests/unit/flashcards/test_job_planning.py tests/contract/flashcards/test_work_plan_vectors.py tests/adversarial/test_flashcard_context_budget.py`: focused tests pass.
- `.venv/bin/python -m pytest`: global offline suite and release 1.1/1.2 contract suites remain green.
- `.venv/bin/python -m ruff check src/study_agent/flashcards tests/unit/flashcards tests/contract/flashcards tests/adversarial/test_flashcard_context_budget.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Model calls, artifact decisions, JobStore mutation, review verdicts, Cardine curriculum/learner policy, and edits outside listed paths.

## Invariants

- Plans are proposals for Job execution, never accepted artifacts.
- Child identity is stable and bounded by HR-01/03 limits.
- Existing planning code may adapt but cannot own a second identity or partial-result rule.

## Stop Conditions

- Stop if context/candidate limits or child identity need a new policy value.
- Stop if a failed cluster would be hidden or automatically accepted.

## Review Gate

Focused tests and independent semantic review are separate gates before HR-07.

## Notes / Handoff

- HR-07 composes these plans as coordinator/leaf/reviewer/assembler Jobs.
