# Task Bead: hr-05-lifecycle-convergence One runtime lifecycle owner

Status: Open
Priority: P1
Type: task
Depends On: hr-04-decision-trace
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Capability and playbook execution route through JobRuntime, parity covers recovery/suspension/continuation/stale/replay, named generic outer transitions are removed after proof, and release 1.1 is published through RuntimeReleaseGate.

## Slice Strategy

migrate

Fresh Context Fit: yes

## Spec Coverage

- HR-05 adapter, parity corpus, exact current-owner/last-consumer inventory, absence scan, and release 1.1.
- README sole lifecycle and transition-removal rules.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-05-lifecycle-convergence.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Fixed migration inventory and parity fixtures fit one fresh Luna xhigh context.

## Context

HR-05 is the only generic lifecycle removal bead. LessonWorker remains for HR-07.

## What To Do

- Add JobRuntimeCapabilityAdapter and proof mapping.
- Migrate tabled integration points and build restart/replay parity fixtures.
- Scan/remove generic lifecycle, playbook, and GenerationWorker outer transitions only after parity; emit 1.1 gate evidence.

## Likely Files / Packages

- src/study_agent/jobs/integration.py
- src/study_agent/capabilities/**
- src/study_agent/hosts/**
- src/study_agent/lifecycle/**
- src/study_agent/playbooks/**
- src/study_agent/workers/**
- tests/parity/test_job_runtime_parity.py
- tests/architecture/test_single_job_lifecycle_owner.py
- tests/integration/test_playbook_engine.py
- tests/integration/test_capability_run_recovery.py
- tests/integration/test_lesson_worker_recovery.py
- tests/integration/test_gateway_worker_proof_recovery.py

## Acceptance Criteria

- [ ] Parity and exact absence report prove one Job outer owner with matching proof fingerprints; LessonWorker remains for HR-07.
- [ ] Generic outer transitions/stores are removed only after all tabled consumers pass; no adapter survives its last consumer.
- [ ] Separate test/absence and independent semantic review gates pass; shared gate publishes 1.1 only.

## Verification

- `.venv/bin/python -m pytest tests/parity/test_job_runtime_parity.py tests/integration/test_playbook_engine.py tests/integration/test_capability_run_recovery.py tests/integration/test_lesson_worker_recovery.py tests/integration/test_gateway_worker_proof_recovery.py tests/architecture/test_single_job_lifecycle_owner.py`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output
- `Clean Python 3.12/3.13 wheel gate through RuntimeReleaseGate: 1.1 only`: expected to pass or produce documented output

## Out Of Scope

- LessonWorker removal, web/sealed workflows, Cardine adapter, state migration, new capabilities, and paths outside the HR-05 inventory.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
