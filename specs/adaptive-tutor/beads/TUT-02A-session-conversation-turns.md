# Task Bead: TUT-02A session conversation turns

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-01

## Outcome

An active session records idempotent general learner turns and verified general
assistant messages without changing any existing event payload or old-stream
projection bytes.

## Acceptance Criteria

- [x] Learner turns reuse strict HUMAN `session.interaction_recorded@1` events.
- [x] `session.assistant_turn_recorded@1` accepts only SERVICE-authored,
  session-scoped `tutor_message@1` output recovered and revalidated by the
  session owner through `PlaybookEngine`.
- [x] Completed/terminated are distinct; no suspended/failed/cancelled/incomplete
  output can be committed as successful.
- [x] Optional reply target is an existing HUMAN interaction in the same session.
- [x] Exact retry is idempotent; changed retry conflicts; stale/race is retryable.
- [x] One run cannot back both a grounded answer and a general assistant turn or
  two general turns anywhere in the course; idempotency remains session-scoped.
- [x] Old course/session projection bytes remain unchanged.
- [x] Local repository, lifecycle observation, export-v1, and exact seven
  StudyTools remain compatible.

## Verification

- Focused session conversation unit/contract/integration tests.
- Full pytest, Ruff, strict mypy, architecture gates, and diff check.

## Out Of Scope

- TutorSnapshot, capability manifests, provider calls, artifacts, assessment,
  planning, UI, and changes to ContinuationSummaryV1.
