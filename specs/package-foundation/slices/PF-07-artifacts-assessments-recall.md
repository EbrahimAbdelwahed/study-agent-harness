# PF-07 — Artifacts, assessments, and recall

## Outcome

The curated facade exposes portable lifecycle contracts for generated study
artifacts, assessment records, and recall scheduling without taking ownership
of Cardine academic policy. Existing replayable proposal, grading, evidence,
enrollment, review, and due-view behavior remains usable through typed ports.

## Non-goals

- No Cardine artifact kinds, curriculum alignment, mastery, readiness, study
  plan, learner eligibility, rating meaning, or substantial-revision policy.
- No sealed Synthetic Verification workflow, coverage reviewer, exam-profile
  approval, or future web-evidence admission.
- No replacement of the canonical event stream with lifecycle-specific stores.

## Exact contracts

- Generic artifact lifecycle has immutable `ArtifactId` and
  `ArtifactRevisionId` values. A revision carries kind-independent content,
  source/citation lineage, producer and validator version pins, input
  fingerprint, and proposal status. Status is one of `PROPOSED`, `ACCEPTED`,
  `REJECTED`, or `SUPERSEDED`.
- Generation and validation never imply acceptance. Only an authorized
  `HUMAN` or injected `SERVICE` policy can append an acceptance/rejection
  decision. Every proposal/revision/decision is an append-only event and
  replays through the shared course stream.
- Artifact content is immutable after proposal. A new substantial revision is
  a new revision ID; historical decisions and citations remain attached to the
  old revision. Harness exposes generic revision metadata and opaque host
  references; Cardine owns artifact-kind semantics and product effects.
- Assessment contracts expose attempt-before-grade ordering, immutable item
  identity, response/grade provenance, deterministic closed grading ports, and
  learner-evidence projections. Grading output is an observation or proposal,
  not an implicit curriculum or mastery mutation.
- Public assessment evidence uses `LearningEvidence`; the generic contract
  carries source/citation references, rubric/policy version, assistance
  metadata supplied by the host, score/outcome, confidence, and event
  sequence. Unsupported claims or missing citations fail closed.
- Recall contracts expose enrollment, review, schedule calculation, and due
  view through `RecallCommandPort`, `RecallViewPort`, and
  `SchedulingPort`. Recall emits replayable observations and applied policy
  version; it does not interpret learner ability or update a Learner Model.
- `RetentionObservation` identifies card/artifact revision, timestamp,
  assistance mode, rating or scored result, and interval metadata. Scheduling
  adapters are optional; the base deterministic policy and in-memory port are
  always offline-capable.
- All durable artifact, assessment, and recall commands use PF-02 authority,
  idempotency, stale-sequence, cancellation, and safe-failure rules. Cardine
  receives typed DTOs through its integration layer rather than raw internal
  objects.

## Probable files

- `src/study_agent/api/artifacts.py`, `api/assessments.py`, and `api/recall.py`
  — curated subfacade exports.
- `src/study_agent/artifacts/contracts.py`, `events.py`, `projection.py`,
  `service.py`, and `ports/artifact.py` — proposal/revision lifecycle.
- `src/study_agent/assessments/contracts.py`, `events.py`, `projection.py`,
  `service.py`, `evidence.py`, and `ports/assessment.py` — attempt/grade and
  LearningEvidence.
- `src/study_agent/recall/contracts.py`, `service.py`, `projection.py`,
  `ports/recall.py`, and `ports/scheduling.py` — ledger and due view.
- `tests/contract/artifacts`, `tests/contract/assessment`,
  `tests/contract/recall`, and the existing lifecycle/replay integration tests.
- `tests/architecture/test_artifact_contract_boundaries.py`,
  `test_assessment_boundaries.py`, and `test_recall_boundaries.py`.

## Dependencies

PF-03 provides canonical events, PF-04 provides storage/replay, PF-05 provides
source/citation lineage, and PF-06 provides permissioned capability dispatch.
PF-08 composes these three domain families into the runtime.

## Removal conditions

Remove parallel lifecycle stores or compatibility DTOs after their consumers
read the shared event stream and facade contracts. Keep no duplicate artifact,
assessment, or recall authority once replay tests pass through the common
projection path.

## Review surface

Review proposal-versus-acceptance boundaries, attempt-before-grade ordering,
source lineage, opaque host IDs, and recall's strict separation from Learner
Model interpretation. Inspect one rejected proposal, one substantial revision,
one contested assessment observation, and one due-view rebuild.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/artifacts tests/contract/assessment tests/contract/recall tests/unit/artifacts tests/unit/assessments tests/unit/recall
uv run --python 3.13 --extra dev pytest -q tests/integration/test_artifact_repository_replay.py tests/integration/test_assessment_ledger_replay.py tests/integration/test_recall_ledger_replay.py tests/integration/test_recall_service.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_assessment_boundaries.py tests/architecture/test_recall_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/artifacts src/study_agent/assessments src/study_agent/recall src/study_agent/ports tests/contract/artifacts tests/contract/assessment tests/contract/recall
git diff --check
```

The focused suite must cover proposal/accept/reject/supersede replay,
attempt-before-grade, citation/provenance validation, idempotent decisions,
recall enrollment/review/due ordering, policy fingerprints, and the absence
of Learner Model or Cardine imports.

## Risks

- Product code may press generic artifact contracts into academic policy. Keep
  kinds, eligibility, and substantial-revision meaning in host-owned opaque
  references.
- Grading can be mistaken for mastery. Keep assessment facts and
  `LearningEvidence` projections separate from any learner model.
- Optional FSRS can become a base dependency. Keep scheduling behind a narrow
  adapter and retain deterministic offline behavior.

## Definition of done

- Artifact, assessment, and recall contracts are importable through typed
  subfacades with no Cardine/product types.
- Proposal acceptance, assessment ordering/provenance, and recall ledger/due
  view replay from shared events with idempotent authority checks.
- Optional schedulers remain optional; offline deterministic fixtures pass.
- Existing domain, integration, architecture, lint, and diff checks pass.
