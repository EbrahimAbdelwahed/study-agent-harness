# Task Bead: TUT-03B capability lifecycle gateway

Status: Done
Priority: P0
Type: expand
Depends On: TUT-03A

## Outcome

One application gateway starts or resumes a host-selected trusted capability
through the existing `PlaybookEngine` and returns the closed public outcome.

## Child Beads

- [TUT-03B1 — inspected and truthfully cancelled playbook runs](TUT-03B1-playbook-inspection-and-cancellation.md)
- [TUT-03B2 — authority-bound capability gateway](TUT-03B2-authority-bound-capability-gateway.md)

## Acceptance Criteria

- [x] Start binds run, capability, exact input, pins, read dependencies,
  authority, and retry identity before effects.
- [x] Resume accepts only the persisted suspended run with identical bindings
  and atomically claims it through the existing CAS path.
- [x] Completed/suspended/terminated/failed engine results retain receipts;
  stale dependency and cancellation are explicit non-success states.
- [x] Cancelled, stale, failed, and incomplete runs cannot be exposed as a
  verified successful output or canonical study artifact.
- [x] The gateway never ranks capabilities, plans an action, or calls a
  provider-specific API.

## Verification

- Lifecycle/idempotency/authority contracts, stale and concurrent-resume
  fixtures, playbook recovery tests, and full gates.
