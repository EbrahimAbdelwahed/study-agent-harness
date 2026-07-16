# Task Bead: TUT-05B deterministic closed grading

Status: Blocked on TUT-05A
Priority: P0
Type: expand
Depends On: TUT-05A

## Outcome

An authority-safe assessment service presents accepted items, records learner
attempts, deterministically grades closed responses, and records contests or
superseding grades through ordered CAS writes without invoking a model.

## Acceptance Criteria

- [ ] `present_item`, `record_attempt`, `grade_closed`, and `contest_grade`
  each append exactly one event using expected course sequence and deterministic
  retry identity; raced noncommits return a typed retryable conflict.
- [ ] Presentation commits before a response can be accepted, and attempt
  commits before grading. A command cannot batch or synthesize an earlier stage.
- [ ] SERVICE alone presents and grades; HUMAN alone records attempts and
  contests; MODEL cannot acquire canonical-write authority.
- [ ] Single-choice and multiple-choice answers compare strict canonical option
  values from the immutable presented item. No case folding, fuzzy matching,
  label guessing, or comma parsing changes the answer.
- [ ] Closed grading derives ordered criterion outcomes and an exact rational
  numerator/denominator from the immutable expected answer and rubric. It does
  not import or call `ModelPort`.
- [ ] Exact retries return the committed result; retry-key drift, duplicate
  attempts, cross-session targets, and reuse of one grade identity for another
  attempt fail closed.
- [ ] A successor grade must name the exact active predecessor for the same
  attempt. The predecessor remains queryable, and a contested grade does not
  contribute as an uncontested active result.
- [ ] No service command emits mastery, scheduling, tutor-policy, or global
  learner state.

## Verification

- Ordering/CAS/idempotency/race unit tests; authority and ownership negatives;
  exact option grading; contest/supersession history; proof that deterministic
  code has no model/provider imports; full offline gates.
