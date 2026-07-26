# KB-17C: Anchor review authority and correspondence

Status: Proposed
Risk: High
Depends On: KB-02, KB-17A, KB-17B
Parent: KB-17

## Outcome

Trusted confirm/re-anchor/reject decisions permanently dominate provisional
extraction, and cross-document figure placement requires explicit
correspondence.

## Acceptance criteria

- [ ] `figure.anchor_reviewed@1` has strict authority, idempotency, target,
  expected-state, and provenance bindings.
- [ ] Rerun reconciliation preserves confirmed/re-anchored/rejected decisions
  and exposes new provisional conflicts without overwriting review.
- [ ] Cross-document anchoring rejects absent, one-sided, expired, cyclic, or
  target-mismatched correspondence.
- [ ] Review queue ordering is deterministic from low confidence and host-unit
  retrieval frequency; it grants no mutation authority.
- [ ] Conflicting concurrent decisions fail closed and replay byte-identically.

## Verification

- Authority/security review, event/reducer/replay tests, concurrent decision
  races, correspondence spoofing, and extractor-rerun adversarial cases.

## Out of scope

- Review UI, automatic acceptance, or semantic cross-document matching.
