# Task Bead: TUT-02 tutor turns and snapshot

Status: In progress
Priority: P0
Type: tracer-bullet
Depends On: TUT-01

## Worker Profile

reuse `session-state-worker` for turn persistence; create a bounded snapshot
worker brief after TUT-01 contracts land

## Outcome

Persist general learner/tutor turns and expose one high-water-marked
`TutorSnapshot` over course, context, sessions, and sources.

## Child Beads

- [TUT-02A — session conversation turns](TUT-02A-session-conversation-turns.md)
- [TUT-02B — sequence-consistent tutor snapshot](TUT-02B-tutor-snapshot.md)

## Acceptance Criteria

- [x] Existing session v1 replay remains valid.
- [x] Assistant turns require a run and typed outcome references.
- [x] Cancelled/incomplete output is not a successful assistant turn.
- [ ] Snapshot reports known, missing, conflicting, and evidence references.
- [ ] Configured CourseProfile hints and learner-statement conflicts retain
  separate attribution and no automatic precedence.
- [ ] Snapshot is byte-identical after mixed replay.

## Verification

- Focused session/snapshot contracts, full pytest, Ruff, strict mypy, diff check.

## Out Of Scope

- Capability selection or any mandatory next-action recommendation.
