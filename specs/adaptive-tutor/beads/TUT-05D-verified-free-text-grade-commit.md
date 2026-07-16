# Task Bead: TUT-05D verified free-text grade commit

Status: Blocked on TUT-05C
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

## Verification

- Verified-port and commit service tests; forged/cross-owner/stale-rubric and
  interrupted-run negatives; exact retry/race behavior; scripted adapter
  integration; architecture and full offline gates.
