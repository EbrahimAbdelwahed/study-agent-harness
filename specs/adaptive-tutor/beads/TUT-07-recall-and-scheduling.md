# Task Bead: TUT-07 recall and scheduling

Status: Blocked on TUT-04 and TUT-05
Priority: P1
Type: tracer-bullet
Depends On: TUT-04, TUT-05

## Worker Profile

create `recall-scheduling-worker`

## Outcome

Accepted flashcards accumulate immutable review history and reproducible due
work through one dependency-free versioned scheduling policy.

## Acceptance Criteria

- [ ] Only accepted flashcards enter recall.
- [ ] Reviews record outcome, latency, confidence, and occurrence time.
- [ ] Applied scheduling decisions pin policy version and history fingerprint.
- [ ] Due queues rebuild deterministically with a fake clock.
- [ ] Anki remains an export adapter.

## Verification

- Scheduler golden tests, review replay/CAS, due queue, export isolation, full gates.
