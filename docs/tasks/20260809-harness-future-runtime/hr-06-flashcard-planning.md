# Task Bead: hr-06-flashcard-planning Hierarchical flashcard work plans

Status: Open
Priority: P1
Type: task
Depends On: hr-01-contract-firewall, hr-03-executor-recovery, hr-05-lifecycle-convergence
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Flashcard work plans are deterministic, bounded, and explicit about partial coverage, with one evidence cluster per leaf, at most six candidates, stable child identity, and visible missing/failure entries.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-06 plan contracts, stable child identity, context/candidate limits, and partial coverage.
- README opaque source refs, no silent omission, and bounded hierarchy.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-06-flashcard-planning.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Deterministic planner and vectors fit one fresh Luna xhigh context.

## Context

HR-06 supplies plans for HR-07 handlers; existing planning cannot own a competing identity or omission rule.

## What To Do

- Add work-plan contracts and deterministic planner.
- Enforce one cluster/leaf, six candidates, context budget, depth 1, and 64 children.
- Add byte-identical golden vectors and explicit partial/failure fixtures.

## Likely Files / Packages

- src/study_agent/flashcards/jobs.py
- src/study_agent/flashcards/planner.py
- tests/unit/flashcards/test_job_planning.py
- tests/contract/flashcards/test_work_plan_vectors.py
- tests/adversarial/test_flashcard_context_budget.py

## Acceptance Criteria

- [ ] Equal inputs yield byte-identical plans and child fingerprints; changed task bytes conflict.
- [ ] Every leaf has one opaque cluster, no more than six candidates, and validated context budget; every failure is visible.
- [ ] Focused planner test gate and independent semantic review gate pass.

## Verification

- `.venv/bin/python -m pytest tests/unit/flashcards/test_job_planning.py tests/contract/flashcards/test_work_plan_vectors.py tests/adversarial/test_flashcard_context_budget.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/flashcards tests/unit/flashcards tests/contract/flashcards tests/adversarial/test_flashcard_context_budget.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Model calls, artifact decisions, JobStore mutation, review verdicts, Cardine policy, learner model, web/sealed workflows, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
