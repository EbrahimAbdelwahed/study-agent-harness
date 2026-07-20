# Slice 01: Progressive study context

## Outcome

A trusted host can append typed learner statements to an existing course,
retract them, explicitly resolve scalar conflicts, and rebuild the identical
context view from events.

## Contract

- Closed statement kinds: objective, deadline, weekly time budget, assessment
  format, and testing preference.
- Objective, assessment format, and testing preference carry trimmed non-empty
  learner text. Deadline carries an ISO calendar date. Weekly time budget carries
  integer minutes in the inclusive range 1..10080. Stored text is stripped at
  its edges and compared byte-for-byte and case-sensitively; dates serialize as
  `YYYY-MM-DD` and minutes as a JSON integer.
- Existing `CourseProfile.learning_goals`, `assessment_styles`, and `exam_date`
  remain immutable setup metadata for v0.2 compatibility. They are not silently
  converted into learner statements. TUT-02 exposes them as separately
  attributed configured hints; disagreement with an active learner statement
  is visible as a configured-context conflict and has no automatic precedence.
- Statements link to a session and originating learner interaction identity.
- The origin must exist in the same course/session and be a HUMAN interaction;
  the statement event repeats both identities in its trusted envelope/payload.
- Deadline and time budget are scalar; distinct active values conflict.
- Objectives, assessment formats, and testing preferences are additive sets.
- No recency rule silently resolves conflicts.
- Only HUMAN or SERVICE actors may append; MODEL is rejected.
- All writes require an idempotency key and use expected course sequence. The
  command identity is course + session + key + command kind: an exact committed
  retry returns its prior result even if the supplied sequence is now stale,
  reuse with changed content is a hard conflict, and a new command with a stale
  sequence is retryable without mutation.
- Resolving a scalar conflict selects one active statement, supersedes the other
  active values, and retains all statement and decision history. A later
  contradictory statement opens a new conflict.
- Retracting the selected winner does not resurrect superseded values.
  Retraction is explicit and historical; it never deletes a statement.
- All three mutations are session-scoped and accept only HUMAN/SERVICE actors.
  Only recording requires an originating HUMAN interaction. Retraction targets
  an active statement. Resolution requires a current scalar conflict and an
  active winner. A new command against an inactive/no-longer-conflicted target
  is rejected; an exact retry of the already committed command is idempotent.
- Repeated equal additive declarations remain distinct statements with distinct
  provenance. The view may deduplicate their values but exposes every supporting
  statement identity.
- Exact event schemas are `study_context.statement_recorded@1`,
  `study_context.statement_retracted@1`, and
  `study_context.conflict_resolved@1`. The service exposes
  `StudyContextCommandError`, `StudyContextConflictError`, and
  `RetryableStudyContextConflictError`.
- Events may carry a typed `causation_id` so later capability executions retain
  provenance; causation never grants authority and may not self-reference.
- Public commands are `record(statement, origin_interaction_id, context,
  expected_sequence)`, `retract(statement_id, context, expected_sequence)`, and
  `resolve(kind, selected_statement_id, context, expected_sequence)`; each
  returns the projection-backed `StudyContextSnapshot` after its event.
- Export-v1 continues to export the generic event ledger after strictly
  validating the new context events.

## Verification

- Strict codec/envelope and malformed-event tests.
- Idempotent retry, changed-command conflict, and stale-sequence tests.
- A→B conflict, explicit winner, retraction, mixed-event replay, and orphan
  course rejection.
- Full offline suite, Ruff, and strict mypy.
