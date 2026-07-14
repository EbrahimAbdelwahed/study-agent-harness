# ADR-0005: Extend the session owner for tutor conversation

Date: 2026-07-14
Status: Accepted

## Context

The existing session owner records learner interactions only as part of grounded
answer finalization and requires every assistant `InteractionRecord` to own a
grounded `AnswerRecord`. An adaptive tutor also needs ordinary learner turns and
validated assistant messages without creating a second canonical conversation.

Changing the strict payload or projection manifest of existing session v1 events
would change replay bytes for released streams. A generic outcome-reference map
would instead predeclare TUT-03 and weaken validation.

## Decision

- Reuse unchanged `session.interaction_recorded@1` HUMAN events for general
  learner turns.
- Add `session.assistant_turn_recorded@1` under the existing session owner for
  general assistant messages.
- Store new assistant records in an additive projection key that is absent from
  streams containing only existing events, preserving old projection bytes.
- A general assistant message is derived from a revalidated
  `VerifiedRunRecord`. Its exact `tutor_message@1` output supplies status,
  content, and optional learner interaction linkage; callers cannot separately
  assert success.
- Only completed or validator-terminated runs may become canonical assistant
  turns. Suspended, cancelled, incomplete, and failed work remains operational
  and cannot be recorded as successful output.
- TUT-02B builds one ordered tutor timeline from the captured course event tuple;
  it does not create a second conversation aggregate.

## Consequences

- Existing grounded answers and session projections retain their exact schemas.
- The tutor timeline can include old grounded answers and new general turns.
- Capability-specific outcomes remain deferred to TUT-03; TUT-02 references only
  the closed verified `tutor_message@1` run output.
- ContinuationSummaryV1 remains the grounded-answer summary. General continuity
  is provided by TutorSnapshotV1 rather than weakening SummaryExchange.

## Alternatives Considered

- Separate tutor-turn stream/owner: rejected because it creates two canonical
  conversations for one session.
- Make `InteractionRecord.answer_id` optional: rejected because old projection
  shapes and grounded-answer invariants would become ambiguous.
- Persist arbitrary host-declared status/content: rejected because the host
  could promote incomplete model output to canonical success.
