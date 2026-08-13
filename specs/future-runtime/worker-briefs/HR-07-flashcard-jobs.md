# Worker Brief: HR-07

## Assignment

Implement `HR-07-flashcard-jobs` from `specs/future-runtime/slices/HR-07-flashcard-jobs.md`.

Worker target: Luna xhigh. This is the only LessonWorker removal bead.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-07-flashcard-jobs.md`
- `specs/future-runtime/beads/HR-07-flashcard-jobs.md`
- The exact LessonWorker owner/last-consumer table and HR-05 removal inventory

## Scope

You may change:

- `src/study_agent/flashcards/job_handlers.py`
- Only bounded reducer/parity adapters under `src/study_agent/flashcards/`
- Proposal-boundary extensions under `src/study_agent/artifacts/`
- `tests/integration/test_flashcard_job_hierarchy.py`
- `tests/integration/test_flashcard_partial_proposals.py`
- `tests/evals/test_hierarchical_flashcard_fixtures.py`
- `tests/architecture/test_flashcard_job_boundaries.py`
- `tests/integration/test_headless_artifact_flow.py`

Do not change:

- Generic lifecycle/playbook/GenerationWorker transitions, Cardine artifact policy, learner estimates, trace exports, provider dependencies, and paths outside the HR-07 table/allowlist.

## Requirements

- Run coordinator, leaf, independent reviewer, and assembler as Job handlers; keep ArtifactService as proposal/revision/decision owner.
- Keep failed/missing clusters and candidate conflicts visible; fetch source spans only for targeted conflicts.
- Scan every LessonWorker symbol/consumer named by HR-07; remove only LessonWorker outer transitions/store/router/bridge after parity and restart proof.
- Add release 1.2 evidence through the shared RuntimeReleaseGate.

## Acceptance Criteria

- Job hierarchy, partial proposal, replay/export, and exact absence tests pass; no automatic acceptance or silent omission occurs.
- Separate test/absence, independent semantic/reviewer, and release gates pass; release 1.2 only.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/integration/test_flashcard_job_hierarchy.py tests/integration/test_flashcard_partial_proposals.py tests/evals/test_hierarchical_flashcard_fixtures.py tests/architecture/test_flashcard_job_boundaries.py tests/integration/test_headless_artifact_flow.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, Job/proposal/removal behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
