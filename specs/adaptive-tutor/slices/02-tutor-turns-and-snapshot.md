# Slice 02: Tutor turns and snapshot

## Outcome

General learner and tutor turns persist independently of grounded-answer
success, while one sequence-consistent snapshot composes course, context,
session, and materials without prescribing next action.

## Contract

- Existing session v1 replay remains valid.
- TUT-02A reuses unchanged `session.interaction_recorded@1` HUMAN events for
  learner turns and adds `session.assistant_turn_recorded@1` for general
  assistant messages. Old-only streams retain byte-identical projections.
- Learner writes require an active owned session, HUMAN/SERVICE authority, a
  mandatory idempotency key, deterministic identity, and expected-sequence CAS.
- Assistant writes require SERVICE authority. The session owner calls
  `PlaybookEngine.recover(...)` with the run identity and pinned execution
  contract; the recovered record's exact `outputs.tutor_message` object is
  `{schema_version: 1, status: completed|terminated, content,
  in_reply_to_interaction_id}` and must agree with the verified run status.
- Assistant turns retain a typed `VerifiedRunOutputRef(run_id,
  output_key='tutor_message', output_fingerprint)`; callers cannot supply
  content or success separately from the verified output.
- Suspended, cancelled, incomplete, and failed work produces no canonical
  successful assistant turn. Validator-terminated user-visible output remains
  explicitly `terminated`, never `completed`.
- Exact committed retry resolves before sequence comparison; changed content,
  run, output, or reply linkage under the same identity conflicts. New stale
  commands are retryable without mutation. A run can own at most one assistant
  turn or grounded answer in the course; idempotency keys remain session-scoped.
- Public TUT-02A types are `AssistantTurnStatus`, `VerifiedRunOutputRef`, and
  `AssistantTurnRecord`. The owner exposes
  `SessionTurnService.record_learner_turn(content, context,
  expected_sequence)` and a keyword-only `record_assistant_turn(context,
  engine, run_id, definition, inputs, pins, expected_sequence,
  read_dependencies=())`, plus a projection-backed `AssistantTurnViewPort`.
- Snapshot reports known, missing, and conflicting context with high-water
  sequence and evidence references.
- Immutable CourseProfile study fields are reported as configured hints with
  their own attribution. Disagreement with learner statements is visible and
  neither source silently wins.
- Capability advertisements are composed by the host after TUT-03; snapshot v1
  does not predeclare a gateway contract that does not yet exist.
- TUT-02B captures one immutable event tuple, replays it once, and derives
  `TutorSnapshotV1` from that projection. It never composes independently-live
  view calls.
- Snapshot v1 contains course/session identity, high-water sequence, configured
  hints, five learner-context fields, exact hint divergences, ordered learner/
  assistant turns, notes, and current material summaries. It contains no next
  action, hypothesis, mastery, or capability advertisement.
