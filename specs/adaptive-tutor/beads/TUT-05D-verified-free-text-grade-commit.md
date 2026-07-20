# Task Bead: TUT-05D verified free-text grade commit

Status: Done
Priority: P0
Type: expand
Depends On: TUT-05C

## Outcome

A narrow proof adapter converts a completed `grade_response@1` run into a
verified outcome that the assessment service can commit as an immutable grade
for its exact prior free-text attempt.

## Acceptance Criteria

- [ ] A provider-neutral verified-grade port exposes only completed validated
  output and sanitized capability/run/prompt/model/validator proof. Gateway,
  model, adapter, and proof-store owners remain outside canonical assessment
  events, reducers, and services.
- [ ] `record_verified_grade` binds run, course, session, attempt, presentation,
  immutable rubric fingerprint, manifest/definition pins, output, and proof
  before emitting `assessment.grade_recorded@1`.
- [ ] Failed, cancelled, suspended, stale, terminated, incomplete, forged,
  cross-course, cross-session, cross-attempt, or stale-rubric executions cannot
  commit.
- [ ] One verified run cannot grade two attempts. Exact retries are idempotent;
  identity or proof drift fails closed.
- [ ] A regrade names the exact active contested predecessor for the same
  attempt and appends a successor without deleting or rewriting prior grade or
  contest history.
- [ ] Technical model provenance is retained, while credentials, provider
  selection policy, raw scratch traces, and unrelated tutor/session context are
  absent.

## Reviewed implementation constraints

- Reuse the existing isolated gateway worker and sanitized
  `VerifiedChildExecutionProof`; add only the closed `grade_response` worker
  task kind and a narrow trusted task factory.
- A durable owner receipt binds one completed child run to exactly one course,
  session, attempt, presentation, accepted revision, prepared-scope fingerprint,
  task, worker receipt, and proof. The registry is idempotent for identical bytes
  and rejects reuse or drift.
- The verified-grade adapter reloads the owner, exact task/receipt/proof, and the
  prepared scope captured by the verified tool output. It re-resolves immutable
  evidence and reconstructs the final validated output without a model call.
- `record_verified_grade` accepts only that inward verified outcome, checks the
  current attempt/rubric/active predecessor, then appends one grade event through
  the existing CAS/idempotency path. No raw output or caller-authored provenance
  overload is allowed.
- The canonical event keeps the sanitized proof fields already modeled by
  `VerifiedCapabilityGradeProvenance`; confidence and evidence handles remain in
  the verified operational proof and do not widen the ledger in this bead.

## Verification

- Verified-port and commit service tests; forged/cross-owner/stale-rubric and
  interrupted-run negatives; exact retry/race behavior; scripted adapter
  integration; architecture and full offline gates.
