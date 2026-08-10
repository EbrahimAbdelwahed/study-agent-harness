# HR-05 — One Runtime Lifecycle Owner

## Outcome

Route capability and playbook execution through the Job lifecycle while keeping
existing checkpoints as subordinate execution proofs. Prove behavioral parity
for recovery, suspension, continuation, and gateway outcomes, then remove
specialized outer lifecycle ownership.

## Non-goals

No new worker capability, web evidence, sealed assessment, Cardine adapter, or
canonical state migration. No parallel Job and lesson/run state machines after
the removal gate.

## Contract and API seam

`src/study_agent/jobs/integration.py:JobRuntimeCapabilityAdapter` wraps the
existing generic lifecycle, playbook engine, and GenerationWorker as bounded
executors. Job transitions are canonical for outer execution; existing proof
records carry child/checkpoint evidence only. HR-05 does not remove or rewrite
flashcard LessonWorker transitions; HR-07 owns that seam. Parity compares
status, retry, continuation, stale, and replay outcomes on the same scripted
inputs.

The current outer-transition owners and their last consumers are fixed by the
repository audit:

| Current owner | Symbols that currently transition state | Last consumers to migrate | HR-05 absence check after migration |
| --- | --- | --- | --- |
| `src/study_agent/lifecycle/service.py`, `src/study_agent/lifecycle/planner.py`, and `src/study_agent/lifecycle/contracts.py` | `LifecycleService.apply`, `plan_lifecycle`, `LifecycleApplyStatus` | `src/study_agent/cli/commands.py:handle_manifest_apply` and `src/study_agent/cli/lifecycle.py:LocalLifecycleInputs.plan`/`LocalLifecycleRuntime` | No Job path calls `LifecycleService.apply` or writes `LifecycleApplyStatus`; planning remains only a subordinate observation proof until its last CLI consumer moves |
| `src/study_agent/playbooks/engine.py`, `src/study_agent/playbooks/runtime.py`, and `src/study_agent/playbooks/contracts.py` | `PlaybookEngine.execute`, `PlaybookEngine.resume`, `_run`, `RunStatus`, `PlaybookRunStatus` | `src/study_agent/capabilities/gateway.py:StudyCapabilityGateway`, `src/study_agent/sessions/{service.py,turn_service.py}`, `src/study_agent/application/grounding_ask.py`, and `src/study_agent/cli/repository.py:_EngineFactory.create` | No Job path writes playbook outer `RunStatus`/`PlaybookRunStatus`; checkpoints/traces remain subordinate evidence |
| `src/study_agent/workers/service.py` + `src/study_agent/workers/contracts.py` | `GenerationWorkerService.start`, `resume`, `_persist_observation`, `GenerationWorkerStatus` | `src/study_agent/flashcards/lesson_worker_service.py`, `src/study_agent/capabilities/{hybrid_flashcards.py,morphology_flashcards.py}`, `src/study_agent/artifacts/verified_batch.py`, `src/study_agent/exams/worker.py`, and `src/study_agent/capabilities/worker_adapter.py` | No Job path writes `GenerationWorkerStatus`; receipts/proofs remain child evidence and LessonWorker is checked by HR-07 |

The parity fixture records the old owner, migrated Job state, and subordinate
proof fingerprint for every last consumer. A consumer is not removed until it
loads the Job result and the same proof fingerprint after restart.

## Files and tests

- Add the Job-to-capability adapter and explicit proof mapping.
- Update only integration points in `src/study_agent/capabilities/`,
  `src/study_agent/hosts/`, `src/study_agent/lifecycle/`,
  `src/study_agent/playbooks/`, and `src/study_agent/workers/`; do not modify
  `src/study_agent/flashcards/lesson_worker_service.py` transitions in HR-05.
- Add `tests/parity/test_job_runtime_parity.py` and
  `tests/architecture/test_single_job_lifecycle_owner.py`.
- Add an absence/last-consumer report to the architecture test that scans the
  exact modules and symbols in the table, rejects specialized outer writes or
  dual Job/specialized commits, and permits only subordinate checkpoint/proof
  fields.

## Dependencies

HR-02, HR-03, and HR-04. HR-06 and HR-07 require this lifecycle owner.

## Removal condition

After parity passes, remove only generic lifecycle, playbook, and
GenerationWorker outer transitions and stores from their named last consumers.
Retain subordinate checkpoints/proofs and canonical Job owner data. Delete
each adapter once the table's last consumer uses JobRuntime. LessonWorker
outer transitions and its removal are explicitly out of HR-05 and remain for
HR-07.

## Review surface

Review the ownership table, transition translation, continuation recovery, and
the deletion diff for old stores. The absence report must show one Job outer
state machine, no generic lifecycle/playbook/GenerationWorker dual write, and
no HR-05 deletion of LessonWorker transitions.

## Exact verification

```bash
.venv/bin/python -m pytest tests/parity/test_job_runtime_parity.py tests/integration/test_playbook_engine.py tests/integration/test_capability_run_recovery.py tests/integration/test_lesson_worker_recovery.py tests/integration/test_gateway_worker_proof_recovery.py tests/architecture/test_single_job_lifecycle_owner.py
```

The architecture test must run an exact symbol scan (including
`LifecycleService.apply`, `plan_lifecycle`, `PlaybookEngine.execute`/
`resume`, `GenerationWorkerService.start`/`resume`/`_persist_observation`,
and the three status enums), enumerate each table consumer, and fail if any
specialized owner performs an outer transition or canonical commit. It must
also assert that `LessonWorkerService` remains the sole unremoved flashcard
outer owner for HR-07.

Then run full offline pytest, Ruff, and mypy. The shared release gate builds
and clean-installs the wheel, and HR-05 publishes release `1.1` through that
gate.

## Risks

Existing recovery behavior may hide state in specialized stores. The parity
corpus must cover restart, lost output, stale continuation, duplicate delivery,
and provider failure before deletion is accepted.

## Definition of done

All parity cases converge through JobRuntime; no canonical dual write remains;
generic lifecycle/playbook/GenerationWorker outer transitions are removed only
after their tabled consumers pass; subordinate proofs remain inspectable;
LessonWorker transitions remain for HR-07; and the shared release gate
publishes `1.1` through HR-05.
