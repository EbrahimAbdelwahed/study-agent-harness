# HR-06 — Hierarchical Flashcard Work Plans

## Outcome

Define deterministic coordinator/leaf work plans for bounded flashcard
generation. Each leaf receives one evidence cluster, produces at most six
candidates under a declared context budget, and names every missing cluster or
failure in partial results.

## Non-goals

No model invocation, artifact acceptance, review verdict, JobStore mutation,
Cardine curriculum alignment, learner model, or automatic omission of failed
clusters.

## Contract and API seam

`src/study_agent/flashcards/jobs.py` defines `FlashcardWorkPlan`,
`EvidenceClusterRef`, `LeafTask`, `CandidateLimit`, and `PartialCoverage`.
`src/study_agent/flashcards/planner.py:plan_flashcard_jobs` computes stable
child identity from parent, position, and task fingerprint. Context budgets and
candidate caps are validated before execution. Opaque source/citation refs are
preserved; no academic concept policy is inferred.

## Files and tests

- Add planner/contracts under `src/study_agent/flashcards/`.
- Add `tests/unit/flashcards/test_job_planning.py`,
  `tests/contract/flashcards/test_work_plan_vectors.py`, and
  `tests/adversarial/test_flashcard_context_budget.py`.

## Dependencies

HR-01 contracts, HR-03 identity/retry, and HR-05 lifecycle owner. HR-07
implements these plans as Jobs.

## Removal condition

Existing `flashcards/planning.py` remains only as an adapter until HR-07 parity;
it must not define a competing child identity or silent partial semantics.

## Review surface

Review cluster ordering, child fingerprints, six-candidate cap, context budget,
depth/child limits, and partial coverage JSON.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/flashcards/test_job_planning.py tests/contract/flashcards/test_work_plan_vectors.py tests/adversarial/test_flashcard_context_budget.py
```

Then run full offline pytest and the release 1.1/1.2 contract suites.

## Risks

Unstable clustering or implicit omission will make replay and learner coverage
untrustworthy. Golden vectors must pin ordering, fingerprints, caps, and all
missing-cluster entries.

## Definition of done

The same input yields byte-identical plans; each leaf has one cluster and at
most six candidates; partial output is explicit; no plan can exceed hierarchy
limits or carry Cardine policy.
