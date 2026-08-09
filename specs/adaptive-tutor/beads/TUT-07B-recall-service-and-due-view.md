# Task Bead: TUT-07B authority-safe recall service and due view

Status: Done — authority-safe service and single-HWM due view verified 2026-07-24
Priority: P1
Type: expand
Depends On: TUT-07A

## Outcome

An authority-safe service enrolls accepted flashcard revisions, atomically
records reviews with their next scheduling decisions, and exposes a
deterministic fake-clock-testable due queue.

## Acceptance Criteria

- [ ] `enroll` validates the exact current accepted flashcard revision, calls
  the scheduler port with empty history, and appends one initial
  `schedule_applied` event through expected-sequence CAS.
- [ ] `review` validates enrollment and the still-current accepted revision,
  constructs the complete ordered history from canonical events, calls the
  scheduler before persistence, then atomically appends
  `review_recorded -> schedule_applied` in one event-store CAS operation.
- [ ] HUMAN authority records the review evidence and SERVICE authority applies
  the scheduling result through a trusted host command boundary. MODEL cannot
  write either event or supply execution context.
- [ ] The service recomputes and verifies policy, history, and result
  fingerprints; stale, forged, cross-course/session/revision, regressive-time,
  non-finite, or secret-shaped scheduler output fails before append.
- [ ] Exact retries return the committed snapshot. Retry-key drift, raced
  noncommits, duplicate enrollment/review, or a different scheduler result for
  an existing identity fail with typed conflicts.
- [ ] The due view reads artifact and recall state from one projection high-water
  mark, includes only currently accepted flashcard revisions with latest
  `due_at <= clock.now()`, and orders by
  `(due_at, artifact_id, revision_id)`.
- [ ] Due reads never call the scheduler, append events, or mutate state.
  Advancing a fake clock alone changes due eligibility deterministically.
- [ ] A deterministic fake scheduler implements the port for offline service,
  CAS, and due-view tests without installing `fsrs`.

## Verification

- Service authority/ordering/CAS/idempotency tests; atomic append failure and
  race fixtures; fake-policy conformance; fake-clock due golden tests;
  supersession filtering; full offline gates.
