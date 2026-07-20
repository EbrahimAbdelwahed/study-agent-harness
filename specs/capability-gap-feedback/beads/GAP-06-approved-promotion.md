# Task Bead: GAP-06 maintainer decision and accepted promotion

Status: Approved — blocked on GAP-05C implementation
Priority: P1
Type: expand
Depends On: GAP-05C

## Outcome

One maintainer resolution can reject, defer, merge as duplicate, or accept the
already-visible proposal; only acceptance promotes it into normal approved
Flywheel execution artifacts and an authorized implementation goal.

## Slice Strategy

expand

Fresh Context Fit: yes

## Spec Coverage

- Minimum-HITL controlled promotion with normal engineering gates.

## Grilling Evidence

- Session/artifact: GAP-05C decision request and immutable proposal.
- Decision state: scope approved 2026-07-18; implementation dependency remains.
- ADR/glossary changes: proposal-specific ADRs only when accepted.

## Worker Profile

reuse `implementer`; require `reviewer`

Rationale: deterministic workflow-state transition, not feature implementation.

## What To Do

- Pin resolution authority and exact `duplicate|rejected|deferred|accepted`
  transitions.
- On acceptance only, finalize the reviewed spec/ADR/beads, run required grills,
  create the goal, and dispatch dependency-ready work through existing gates.
- Preserve links from report aggregate through proposal, decision, beads,
  reviews, and eventual release/resolution.

## Acceptance Criteria

- [ ] Retry/race/process loss cannot promote twice or change the chosen proposal.
- [ ] One resolution affects only the immutable gap key/cohort shown in that
  decision; unrelated reports require separate decisions.
- [ ] Reject/defer/duplicate never create implementation work.
- [ ] Acceptance cannot skip worker briefs, tests, semantic review, or existing
  publication authority and cannot merge/release/deploy by itself.
- [ ] New unresolved technical choices create a blocking decision rather than an
  inferred implementation.

## Verification

- All resolution branches, exact retry, race/process loss, stale proposal,
  missing grill/review, and end-to-end Flywheel validation.

## Out Of Scope

- Feature-specific code, GitHub synchronization, merge, release, or deployment.
