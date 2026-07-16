# Task Bead: TUT-04E1 verified generated-batch commit

Status: In Progress (proof conversion and owner wiring complete; composition/media pending)
Priority: P0
Type: expand
Depends On: TUT-04B, TUT-04C0B1A, TUT-04C3, TUT-04D

## Outcome

The artifact service proof port is backed by persisted verified child capability
runs and lesson/exam coordinator receipts, so generated content/provenance cannot
be caller-forged.

## Acceptance Criteria

- [ ] Adapter consumes the B1A sanitized `VerifiedChildExecutionProof` using
  exact task, child-run, worker-receipt, and the child context derived through
  `generation_worker_child_context`; it never substitutes the parent context or
  duplicates context/authority derivation. It reconstructs batch,
  profile selection, pins, prompt/validator receipts, bounded technical model
  receipt (adapter/version/model/response/optional usage), dependencies, output
  fingerprint, and canonical source commitments.
- [ ] B1A technical model `response_id` is provider-neutrally nullable. E1 must
  widen artifact `ModelProvenance` to nullable or make another explicitly
  approved contract change; it must never invent an id or reject an otherwise
  verified B1A proof merely because the adapter supplied `None`.
- [ ] For lesson generation, the adapter verifies the parent plan/coordinator
  fingerprint, canonical child order, active bundle identity, and membership of
  the selected child run. The UI may commit accepted pages independently, but no
  caller can splice a run from another lesson/profile/plan.
- [ ] Temporary candidate keys resolve to deterministic artifact/revision IDs
  and parent links before one proposal-batch append per verified child page;
  cross-page overview association remains verified coordinator metadata and is
  never smuggled into the same-batch parent ordinal.
- [ ] Exam-blueprint commits use the same verified-proof path from TUT-04D;
  neither lesson nor exam generated output receives a raw caller-forgeable
  commit bypass.
- [ ] Failed, suspended, terminated, cancelled, stale, tampered, or mismatched
  runs cannot append; exact retry does not repeat model/search or event effects.

## Verification

- Verified-child/parent-plan, partial-page acceptance, overview association,
  process-loss/idempotency/tamper/source-drift integration and full gates.

## Lesson-side readiness

- `LessonWorkerService.review_completed` now publishes an exact inward owner
  commitment only after every page batch, coverage rule, canonical ordering,
  overview association, child task, and worker receipt have been reverified.
- The non-optional owner writer receives the exact task, completed receipt, and
  parent context. Its adapter must load the existing B1A proof and idempotently
  create `LessonGeneratedBatchOwnerReceipt`; the coordinator verifies returned
  child task/receipt/proof and owner fingerprints and never fabricates proof
  identity. An unconfigured writer fails completed review closed.
- The lesson/exam owner writers, strict registry, proof conversion adapter, and
  source-drift-checking resolver are implemented. Exam owner receipts persist
  exact canonical task/receipt bytes and never the raw opaque request key.
- Remaining E1 work is runtime composition with a profile-aware historical
  lesson-detail router and persistence of the exact trusted morphology-media
  receipt. Media-bearing pages currently fail closed rather than weakening the
  verified chain.
