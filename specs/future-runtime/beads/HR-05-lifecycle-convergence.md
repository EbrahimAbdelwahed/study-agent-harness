# Task Bead: HR-05 One runtime lifecycle owner

Status: Open
Priority: P1
Type: task
Depends On: HR-04-decision-trace

## Outcome

Capability and playbook execution route through JobRuntime with existing checkpoints as subordinate proofs. Parity covers recovery, suspension, continuation, stale, retry, and gateway outcomes; then the named generic lifecycle, playbook, and GenerationWorker outer transitions are removed and release 1.1 is published through the shared RuntimeReleaseGate.

## Slice Strategy

migrate

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-05-lifecycle-convergence.md`: adapter, parity corpus, exact current-owner/last-consumer inventory, absence scan, and release 1.1 gate.
- `specs/future-runtime/README.md`: sole lifecycle and transition-removal rules.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-05-lifecycle-convergence.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a repository-local migration with a fixed consumer inventory and parity fixtures. Execute in one fresh Luna xhigh context.

## Context

HR-05 is the only generic lifecycle removal bead. `LifecycleService`, playbook outer statuses, and `GenerationWorkerStatus` are removed only after every tabled last consumer loads Job results and matching proof fingerprints after restart. LessonWorker remains for HR-07.

## What To Do

- Add `JobRuntimeCapabilityAdapter` and proof mapping; migrate only the integration points listed by HR-05.
- Build parity fixtures for restart, lost output, stale continuation, duplicate delivery, provider failure, suspension, retry, and replay.
- Add the exact symbol/consumer absence report from the HR-05 table; remove generic outer transitions/stores after parity, preserving subordinate proofs.
- Implement the shared RuntimeReleaseGate evidence and publish release 1.1 through HR-05.

## Likely Files / Packages

- `src/study_agent/jobs/integration.py`: JobRuntimeCapabilityAdapter and proof mapping.
- `src/study_agent/capabilities/**`, `src/study_agent/hosts/**`, `src/study_agent/lifecycle/**`, `src/study_agent/playbooks/**`, `src/study_agent/workers/**`: only tabled integration/removal points.
- `tests/parity/test_job_runtime_parity.py`: parity corpus.
- `tests/architecture/test_single_job_lifecycle_owner.py`: exact symbol, last-consumer, and absence report.
- `tests/integration/test_playbook_engine.py`, `tests/integration/test_capability_run_recovery.py`, `tests/integration/test_lesson_worker_recovery.py`, `tests/integration/test_gateway_worker_proof_recovery.py`: regression gates.

## Acceptance Criteria

- [ ] All parity fixtures converge through JobRuntime with identical status, retry, continuation, stale, replay, and subordinate proof fingerprints after restart.
- [ ] The exact HR-05 current-owner/last-consumer inventory is scanned; no Job path writes generic outer statuses or dual canonical outcomes, and LessonWorker transitions remain untouched for HR-07.
- [ ] Generic lifecycle, playbook, and GenerationWorker outer transitions/stores are removed only after their listed consumers pass; no adapter remains after its last consumer.
- [ ] Focused parity/absence tests pass as a test gate; an independent semantic review confirms the inventory and removal diff; the shared RuntimeReleaseGate publishes only release 1.1.

## Verification

- `.venv/bin/python -m pytest tests/parity/test_job_runtime_parity.py tests/integration/test_playbook_engine.py tests/integration/test_capability_run_recovery.py tests/integration/test_lesson_worker_recovery.py tests/integration/test_gateway_worker_proof_recovery.py tests/architecture/test_single_job_lifecycle_owner.py`: focused parity and absence pass.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m mypy`: repository gates pass.
- `git diff --check`: clean.
- Clean Python 3.12/3.13 wheel gate through the shared RuntimeReleaseGate: release 1.1 only.

## Out Of Scope

- Flashcard LessonWorker removal, web/sealed workflows, Cardine adapter, canonical-state migration, new capabilities, and edits outside the listed inventory.

## Invariants

- Job is the only outer lifecycle; checkpoints/traces are subordinate evidence.
- LessonWorker remains the sole unremoved flashcard outer owner until HR-07.
- Release 1.1 is emitted only by the shared gate after HR-05 evidence passes.

## Stop Conditions

- Stop before removal if any listed consumer lacks parity proof or if the absence scan finds a dual writer.
- Stop and report if a deletion would touch LessonWorker transitions or canonical product policy.

## Review Gate

Test/absence gate and independent semantic review are separate prerequisites for the 1.1 release gate.

## Notes / Handoff

- HR-06, HR-07, HR-08, HR-09, HR-10, and HR-11 depend on this lifecycle owner.
