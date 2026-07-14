# Task Bead: TUT-02A session conversation turns

Status: Ready
Priority: P0
Type: tracer-bullet
Depends On: TUT-01

## Outcome

An active session records idempotent general learner turns and verified general
assistant messages without changing any existing event payload or old-stream
projection bytes.

## Acceptance Criteria

- [ ] Learner turns reuse strict HUMAN `session.interaction_recorded@1` events.
- [ ] `session.assistant_turn_recorded@1` accepts only SERVICE-authored,
  session-scoped `tutor_message@1` output from a VerifiedRunRecord.
- [ ] Completed/terminated are distinct; no suspended/failed/cancelled/incomplete
  output can be committed as successful.
- [ ] Optional reply target is an existing HUMAN interaction in the same session.
- [ ] Exact retry is idempotent; changed retry conflicts; stale/race is retryable.
- [ ] One run cannot back both a grounded answer and a general assistant turn or
  two general turns.
- [ ] Old course/session projection bytes remain unchanged.
- [ ] Local repository, lifecycle observation, export-v1, and exact seven
  StudyTools remain compatible.

## Verification

- Focused session conversation unit/contract/integration tests.
- Full pytest, Ruff, strict mypy, architecture gates, and diff check.

## Out Of Scope

- TutorSnapshot, capability manifests, provider calls, artifacts, assessment,
  planning, UI, and changes to ContinuationSummaryV1.
