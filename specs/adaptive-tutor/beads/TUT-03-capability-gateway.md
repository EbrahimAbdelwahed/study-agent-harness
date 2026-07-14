# Task Bead: TUT-03 capability gateway

Status: In progress
Priority: P0
Type: tracer-bullet
Depends On: TUT-02

## Worker Profile

reuse `sequential-playbook-engine-worker` with a new gateway-specific brief

## Outcome

Discover, start, and resume trusted built-in tutor capabilities through one
closed contract, shipping `explain_concept@1` and `assess_understanding@1`.

## Child Beads

- [TUT-03A — capability contracts and discovery](TUT-03A-capability-contracts-and-discovery.md)
- [TUT-03B — start, suspend, resume, and terminal outcomes](TUT-03B-capability-lifecycle-gateway.md)
- [TUT-03C — built-in tutor capabilities and offline evals](TUT-03C-builtin-capabilities-and-evals.md)

## Acceptance Criteria

- [ ] Outcomes use the closed completed/suspended/terminated/cancelled/stale/failed set.
- [ ] Continuations bind pins, input, read dependencies, authority, and retry identity.
- [ ] Host chooses capability; gateway never plans the next action.
- [ ] Existing seven StudyTools and fingerprints are unchanged.
- [ ] Scripted-model evals cover direct action, minimal clarification, and interruption.

## Verification

- Capability contracts/evals, playbook recovery tests, architecture imports,
  full offline gates.
