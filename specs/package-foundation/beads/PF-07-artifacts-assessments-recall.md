# Task Bead: PF-07 Artifacts, assessments, and recall

Status: Open
Priority: P1
Type: task
Depends On: PF-03, PF-04, PF-05, PF-06

## Outcome

The facade exposes portable artifact proposal/revision decisions, assessment
observations, and recall ledger/due-view contracts over the shared event
stream, without owning Cardine policy or a learner model.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-07 artifact, assessment, evidence, recall, scheduling, replay, and authority criteria in `specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md`.
- README proposal/acceptance, source lineage, canonical stream, and opaque host-reference invariants.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `grounded-study-artifact-worker`

Rationale:

The artifact half requires grounded proposals, provenance, replay, and an
acceptance boundary; the profile explicitly protects those seams. Assessment
and recall remain typed neighboring contracts in the same vertical slice.

## Context

Existing lifecycle families need a curated portable boundary. Harness records
generic facts and observations while the Host supplies artifact kinds,
eligibility, grading meaning, scheduling policy, and learner-model effects.

## Invariants

- Artifact revisions are immutable and status is exactly proposed, accepted, rejected, or superseded; generation/validation never imply acceptance.
- Only authorized HUMAN or injected SERVICE policy appends acceptance/rejection; every proposal, revision, and outcome is an append-only event.
- Assessment enforces attempt-before-grade, immutable item identity, provenance, `LearningEvidence`, and no implicit mastery mutation.
- Recall exposes enrollment, review, scheduling, due view, and `RetentionObservation`; it never interprets learner ability or writes a Learner Model.
- All durable commands use PF-02 authority, idempotency, stale, cancellation, source lineage, and safe-failure rules; Host references remain opaque.

## What To Do

- Implement artifact IDs/revisions, generic content/lineage metadata, proposal/accept/reject/supersede events, and replay projection.
- Implement assessment attempt/response/grade contracts, deterministic grading port, provenance, and `LearningEvidence` projection.
- Implement recall enrollment/review ledger, `RetentionObservation`, scheduling port, deterministic offline policy, and due view.
- Export typed subfacades and add replay, idempotency, policy fingerprint, citation, and architecture tests.

## Likely Allowed Files / Packages

- `src/study_agent/api/artifacts.py`, `api/assessments.py`, `api/recall.py`.
- `src/study_agent/artifacts/**`, `src/study_agent/assessments/**`, `src/study_agent/recall/**`, and named ports.
- `tests/contract/artifacts/**`, `tests/contract/assessment/**`, `tests/contract/recall/**`, unit/integration lifecycle tests, and boundary tests.

## Acceptance Criteria

- [ ] Artifact proposal, acceptance, rejection, supersession, substantial revision metadata, lineage, and replay are typed and shared-stream based.
- [ ] Assessment rejects grade-before-attempt, preserves item/provenance identity, validates citations, and emits `LearningEvidence` without mastery writes.
- [ ] Recall enrollment/review/due ordering is replayable with deterministic policy fingerprints and optional scheduler adapters.
- [ ] Idempotent decisions, stale sequence, cancellation, unsupported claims, missing citations, and unauthorized actor paths fail safely.
- [ ] No Cardine/product imports, artifact-kind assumptions, learner-model writes, parallel canonical stores, or mandatory FSRS dependency exists.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/artifacts tests/contract/assessment tests/contract/recall tests/unit/artifacts tests/unit/assessments tests/unit/recall`: focused contracts pass.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_artifact_repository_replay.py tests/integration/test_assessment_ledger_replay.py tests/integration/test_recall_ledger_replay.py tests/integration/test_recall_service.py`: replay/service tests pass.
- `uv run --python 3.13 --extra dev pytest -q tests/architecture/test_artifact_contract_boundaries.py tests/architecture/test_assessment_boundaries.py tests/architecture/test_recall_boundaries.py`: boundaries pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/artifacts src/study_agent/assessments src/study_agent/recall src/study_agent/ports tests/contract/artifacts tests/contract/assessment tests/contract/recall`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Cardine artifact kinds, curriculum, alignment, mastery, readiness, planning, eligibility, rating meaning, synthetic verification, web admission, UI, and product effects.

## Removal Conditions

- Remove parallel lifecycle stores and compatibility DTOs once all consumers use shared events and facade contracts; retain no duplicate authority.

