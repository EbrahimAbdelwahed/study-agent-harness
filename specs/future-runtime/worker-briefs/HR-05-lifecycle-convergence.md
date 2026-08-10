# Worker Brief: HR-05

## Assignment

Implement `HR-05-lifecycle-convergence` from `specs/future-runtime/slices/HR-05-lifecycle-convergence.md`.

Worker target: Luna xhigh. This is the only generic lifecycle migration bead.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-05-lifecycle-convergence.md`
- `specs/future-runtime/beads/HR-05-lifecycle-convergence.md`
- The exact current-owner/last-consumer table in HR-05 and all named modules before editing

## Scope

You may change:

- `src/study_agent/jobs/integration.py`
- Only tabled integration/removal points under `src/study_agent/capabilities/`, `src/study_agent/hosts/`, `src/study_agent/lifecycle/`, `src/study_agent/playbooks/`, and `src/study_agent/workers/`
- `tests/parity/test_job_runtime_parity.py`
- `tests/architecture/test_single_job_lifecycle_owner.py`
- Tabled regression tests: `tests/integration/test_playbook_engine.py`, `tests/integration/test_capability_run_recovery.py`, `tests/integration/test_lesson_worker_recovery.py`, `tests/integration/test_gateway_worker_proof_recovery.py`

Do not change:

- `src/study_agent/flashcards/lesson_worker_service.py` transitions or HR-07 files, Cardine, canonical-state migration, new capabilities, web/sealed workflows, and paths outside the table/allowlist.

## Requirements

- Route outer capability/playbook/GenerationWorker execution through JobRuntime; preserve checkpoints/proofs and owner idempotency.
- Build parity for restart, lost output, stale continuation, duplicate delivery, provider failure, suspension, retry, and replay.
- Scan every exact symbol and last consumer in HR-05; remove generic outer transitions/stores only after parity and proof fingerprints pass.
- Emit release 1.1 evidence through the shared RuntimeReleaseGate only after separate test and semantic review gates.

## Acceptance Criteria

- Parity and absence report pass with one Job outer owner; LessonWorker remains untouched for HR-07.
- Focused test/absence gate and independent semantic review are separate prerequisites for release 1.1.
- No adapter survives its named last consumer and no canonical dual write remains.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/parity/test_job_runtime_parity.py tests/integration/test_playbook_engine.py tests/integration/test_capability_run_recovery.py tests/integration/test_lesson_worker_recovery.py tests/integration/test_gateway_worker_proof_recovery.py tests/architecture/test_single_job_lifecycle_owner.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, migration/parity behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
