# Task Bead: TUT-02B sequence-consistent tutor snapshot

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-02A

## Outcome

One immutable course-stream capture produces a deterministic TutorSnapshotV1
over configured hints, learner context, one ordered timeline, notes, and current
materials.

## Acceptance Criteria

- [x] Exactly one event-store read supplies projection, timeline, and high-water.
- [x] Existing grounded answers and new general assistant messages normalize into
  one ordered timeline with event evidence.
- [x] CourseProfile hints remain separately attributed from learner statements.
- [x] Exact hint divergences are visible with no inferred equivalence/precedence.
- [x] All five statement kinds report missing, known, or conflicting.
- [x] Material summaries use current revisions from the captured projection only.
- [x] Canonical snapshot bytes rebuild identically after mixed replay.
- [x] No capability, next-action, provider, hypothesis, or mastery field exists.

## Verification

- Snapshot unit/contract tests, one-read race fixture, mixed-replay integration,
  full offline gates.
