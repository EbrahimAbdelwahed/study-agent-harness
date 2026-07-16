# Worker Brief: TUT-04E1 verified proof conversion

## Goal

Recover one generated artifact batch only through its durable owner receipt,
exact coordinator material, and sanitized B1A child proof. Convert verified
flashcard or exam output into canonical proposal content and provenance without
calling a model, gateway, search, or canonical event owner.

## Seams

- `GeneratedBatchOwnerReader` locates the sole strict owner by child `RunId`.
- `GeneratedBatchOwnerResolver` supplies the exact task, completed worker
  receipt, and already-verified lesson checkpoint/prepared scope or exam
  coordinator material. Implementations are responsible for loading durable
  coordinator state; the adapter rechecks every public commitment.
- `VerifiedChildProofReader.load` receives the exact task, child run, receipt,
  and context derived only by `generation_worker_child_context`.
- The adapter implements `recover(child_run_id, context)` and returns the
  existing `VerifiedGeneratedArtifactBatch` contract.

## Conversion rules

- Lesson recovery verifies parent lesson request/plan/profile/coordinator,
  canonical page order and membership, bundle/wrapper/scope/read-set/revision
  commitments, task, receipt, and proof before decoding candidates.
- Temporary candidate keys become contiguous ordinals. A parent key may resolve
  only to an earlier candidate in the same page. Cross-page overview metadata
  stays in the owner receipt and never becomes `parent_ordinal`.
- Exam recovery verifies exact request bytes, opaque-key/coordinator/scope/
  projection/evidence-map commitments and emits one observational blueprint.
- Source commitments and retrieval metadata come only from verified prepared
  evidence; read dependencies, prompt, validators, pins, and technical model
  receipt come only from B1A proof. Nullable `response_id` is copied unchanged.
- Until the exact trusted media receipt is persisted in the proof chain, any
  non-empty media-handle set fails with `UnsupportedVerifiedMediaError`.

## Out of scope

- Runtime composition, acceptance policy, export, and verified-media receipt
  persistence.

## Wiring delivered

- `VerifiedLessonOwnerWriterAdapter` derives the exact child context, reloads
  B1A proof, and idempotently claims the owner registry slot.
- `ExamAnalysisFacade.detail` now requires an owner writer and publishes only
  after prepared scope, prompt projection, evidence mapping, task, receipt, and
  proof have all been verified. The exam owner persists canonical task/receipt
  bytes but only a fingerprint of the opaque request key.
- `VerifiedExamOwnerWriterAdapter` consumes the already-loaded proof without a
  second model/tool execution. `VerifiedGeneratedOwnerResolverAdapter` rebuilds
  lesson material from its checkpoint plus B1 detail, re-resolves every lesson
  citation, and rebuilds exam material through the trusted scope-preparation
  port. Any fingerprint or source-content drift fails closed.
- The remaining composition root must supply a profile-aware
  `PlannedBundleWorker` router for historical hybrid and morphology task detail;
  a single request-bound worker is insufficient after process restart.

## Verification

- Lesson candidate/parent/provenance conversion and child-context assertion.
- Exam observation/evidence-index conversion.
- Owner, task, receipt, proof, coordinator, session, and media fail-closed cases.
- Architecture isolation, Ruff, strict mypy, and focused/full offline tests.
