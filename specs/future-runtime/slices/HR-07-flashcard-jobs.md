# HR-07 — Flashcard Job Composition

## Outcome

Execute coordinator, leaf, independent reviewer, and assembler Jobs. Persist only proposal/revision/decision contracts owned by the artifact lifecycle; never silently omit candidates or auto-accept model output.

## Non-goals

No Cardine artifact kinds or approval policy, learner estimates, trace payloads in artifact exports, or self-reviewing generator.

## Contract and API seam

`src/study_agent/flashcards/job_handlers.py` implements coordinator, leaf, reviewer, and assembler handlers behind `CapabilityExecutor`. Reducers inspect candidates, rubrics, fingerprints, coverage, and references; source spans are fetched only for targeted conflicts. `ArtifactService` remains the proposal/revision/decision owner.

HR-07 is the only slice that removes the flashcard LessonWorker outer
transitions. The current seam and its last consumers are fixed by repository
evidence:

| Current owner | Symbols that currently transition state | Last consumers to migrate | HR-07 absence check after migration |
| --- | --- | --- | --- |
| `src/study_agent/flashcards/lesson_worker_service.py` | `LessonWorkerService.start`, `advance`, `_prepare_page`, `_claim_child`, `_observe_claimed`, `_replace_page`, `_compact`; `LessonWorkerStatus` and `LessonWorkerPageStatus` | `src/study_agent/artifacts/verified_batch.py:VerifiedGeneratedBatchAdapter`, `src/study_agent/artifacts/runtime.py:compose_verified_generated_batch_runtime`, `src/study_agent/flashcards/worker_router.py:ClosedHistoricalPlannedBundleWorkerRouter`, and `LessonWorkerStore`/`PlannedBundleWorker` in `src/study_agent/ports/lesson_worker.py` | No Job handler writes LessonWorker statuses, creates a `LessonWorkerCheckpoint`, or owns `lesson_run_id`; the old service is absent after the final listed consumer migrates |
| `src/study_agent/flashcards/lesson_worker_contracts.py` | `LessonWorkerCheckpoint`, `LessonWorkerPageCheckpoint`, `lesson_run_id`, `child_task_id` | `src/study_agent/artifacts/verified_batch.py`, `src/study_agent/ports/verified_batch.py`, and profile bindings in `src/study_agent/capabilities/{hybrid_flashcards.py,morphology_flashcards.py}` | These values remain only as historical proof/identity inputs while parity runs; no transition write or second outer lifecycle remains |

GenerationWorker transitions are not in this removal table: HR-05 owns their
outer transition removal, while HR-07 consumes the resulting child Job and
retains only its receipt/proof.

## Files and tests

- Add handlers/reducer adapters under `src/study_agent/flashcards/`; extend `src/study_agent/artifacts/` only at its proposal boundary.
- Add `tests/integration/test_flashcard_job_hierarchy.py`, `tests/integration/test_flashcard_partial_proposals.py`, `tests/evals/test_hierarchical_flashcard_fixtures.py`, and `tests/architecture/test_flashcard_job_boundaries.py`.
- Add a parity adapter for the exact LessonWorker modules/symbols in the table
  and an architecture absence report that enumerates every last consumer.

## Dependencies

HR-05 lifecycle, HR-06 work plans, existing artifact contracts, and HR-04 trace hooks.

## Removal condition

After parity, remove only the LessonWorker outer lifecycle and any bridge that
owns its transitions. Keep artifact proposal/revision/decision services and
the HR-05 Job/GenerationWorker child receipts. Delete the LessonWorker store,
router, and adapter only after the table's final consumer loads the same Job
receipt and proof fingerprint after restart.

## Review surface

Review Job graph, reviewer independence, partial coverage, proposal-only
persistence, conflict fetches, and exclusion of operational state from export.
The absence report must prove HR-07 removes no generic lifecycle, playbook, or
GenerationWorker transition and leaves no LessonWorker dual writer.

## Exact verification

```bash
.venv/bin/python -m pytest tests/integration/test_flashcard_job_hierarchy.py tests/integration/test_flashcard_partial_proposals.py tests/evals/test_hierarchical_flashcard_fixtures.py tests/architecture/test_flashcard_job_boundaries.py tests/integration/test_headless_artifact_flow.py
```

Then run full offline pytest, Ruff, mypy, and the release 1.2 clean-wheel gate.

The architecture test must scan `LessonWorkerService.start`/`advance`, the
page transition helpers, both LessonWorker status enums, checkpoint creation,
`lesson_run_id`, and every tabled consumer. It fails if a generic Job module
writes any LessonWorker transition or if a removed consumer still imports the
old service. The shared release gate publishes `1.2` through HR-07.

## Risks

Reducer shortcuts can turn partial work into accepted artifacts. Tests require visible missing clusters, independent review, stable fingerprints, and an explicit artifact decision.

## Definition of done

All Jobs recover through one lifecycle; only LessonWorker outer transitions are
removed in this slice; outputs are proposals only; no silent omission or
automatic acceptance occurs; artifact replay/export is byte-stable; and the
shared release gate publishes `1.2` through HR-07.
