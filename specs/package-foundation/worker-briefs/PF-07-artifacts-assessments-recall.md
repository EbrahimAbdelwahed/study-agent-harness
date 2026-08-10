# Worker Brief: PF-07

## Assignment

Implement `PF-07` from `specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-03 through PF-07 slices, and `specs/package-foundation/beads/PF-07-artifacts-assessments-recall.md`
- existing artifacts, assessments, recall, event, source, capability, and replay modules/tests

## Scope

You may change:

- `src/study_agent/api/artifacts.py`, `api/assessments.py`, `api/recall.py`
- `src/study_agent/artifacts/**`, `src/study_agent/assessments/**`, `src/study_agent/recall/**`, and explicitly named ports
- artifact/assessment/recall contract, unit, integration, and boundary tests named by PF-07

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, product policy/UI/auth, planner or learner-model owners, web evidence, sealed verification, or dependencies

## Invariants and Requirements

- Artifact revisions are immutable and statuses are proposed, accepted, rejected, or superseded; generation and validation never accept.
- Only HUMAN or injected SERVICE appends acceptance/rejection; all proposal/revision/assessment/recall facts use the shared stream.
- Assessment enforces attempt-before-grade, item identity, source/citation provenance, `LearningEvidence`, and no mastery mutation.
- Recall exposes enrollment, review, due view, scheduling, and `RetentionObservation` without learner-model interpretation; scheduler extras remain optional.
- All durable commands use PF-02 authority, idempotency, stale, cancellation, source lineage, and safe-failure rules with opaque Host references.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/artifacts tests/contract/assessment tests/contract/recall tests/unit/artifacts tests/unit/assessments tests/unit/recall
uv run --python 3.13 --extra dev pytest -q tests/integration/test_artifact_repository_replay.py tests/integration/test_assessment_ledger_replay.py tests/integration/test_recall_ledger_replay.py tests/integration/test_recall_service.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_assessment_boundaries.py tests/architecture/test_recall_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/artifacts src/study_agent/assessments src/study_agent/recall src/study_agent/ports tests/contract/artifacts tests/contract/assessment tests/contract/recall
git diff --check
```

## Report Back

Return files changed, artifact/assessment/recall behavior, exact verification,
profile constraints followed, unresolved questions, and follow-up beads.
