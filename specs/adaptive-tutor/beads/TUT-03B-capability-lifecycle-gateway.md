# Task Bead: TUT-03B capability lifecycle gateway

Status: Blocked on TUT-03A
Priority: P0
Type: expand
Depends On: TUT-03A

## Outcome

One application gateway starts or resumes a host-selected trusted capability
through the existing `PlaybookEngine` and returns the closed public outcome.

## Acceptance Criteria

- [ ] Start binds run, capability, exact input, pins, read dependencies,
  authority, and retry identity before effects.
- [ ] Resume accepts only the persisted suspended run with identical bindings
  and atomically claims it through the existing CAS path.
- [ ] Completed/suspended/terminated/failed engine results retain receipts;
  stale dependency and cancellation are explicit non-success states.
- [ ] Cancelled, stale, failed, and incomplete runs cannot be exposed as a
  verified successful output or canonical study artifact.
- [ ] The gateway never ranks capabilities, plans an action, or calls a
  provider-specific API.

## Verification

- Lifecycle/idempotency/authority contracts, stale and concurrent-resume
  fixtures, playbook recovery tests, and full gates.
