# Worker Brief: HR-06

## Assignment

Implement `HR-06-flashcard-planning` from `specs/future-runtime/slices/HR-06-flashcard-planning.md`.

Worker target: Luna xhigh. Execute only this planner bead after HR-05.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-06-flashcard-planning.md`
- `specs/future-runtime/beads/HR-06-flashcard-planning.md`
- HR-01/03 identity contracts and existing `src/study_agent/flashcards/planning.py`

## Scope

You may change:

- `src/study_agent/flashcards/jobs.py`
- `src/study_agent/flashcards/planner.py`
- `tests/unit/flashcards/test_job_planning.py`
- `tests/contract/flashcards/test_work_plan_vectors.py`
- `tests/adversarial/test_flashcard_context_budget.py`

Do not change:

- Paths outside the allowlist, including model adapters, JobStore mutation, artifact acceptance, Cardine curriculum/learner policy, web/sealed workflows, and dependencies.

## Requirements

- Implement deterministic FlashcardWorkPlan, EvidenceClusterRef, LeafTask, CandidateLimit, PartialCoverage, and stable child identity.
- Enforce one cluster/leaf, six candidates, context budget, depth 1, 64 children, and explicit missing/failure entries.
- Preserve opaque source/citation refs; existing planning code cannot create a competing identity or omit failures.

## Acceptance Criteria

- Golden vectors and adversarial budget/omission tests pass with byte-identical plans.
- Separate focused test and independent semantic review gates pass; no model, artifact, or policy behavior is added.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/flashcards/test_job_planning.py tests/contract/flashcards/test_work_plan_vectors.py tests/adversarial/test_flashcard_context_budget.py
.venv/bin/python -m ruff check src/study_agent/flashcards tests/unit/flashcards tests/contract/flashcards tests/adversarial/test_flashcard_context_budget.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, planner behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
