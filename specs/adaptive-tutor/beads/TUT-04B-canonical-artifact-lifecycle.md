# Task Bead: TUT-04B canonical proposal and decision lifecycle

Status: Done
Priority: P0
Type: expand
Depends On: TUT-04A

## Outcome

Grounded artifact batches, revisions, human decisions, trusted-service
decisions, and explicit supersession replay from the per-course event stream.

## Acceptance Criteria

- [x] Strict proposal-batch and decision events preserve immutable lineage,
  source commitments, idempotency, and sequence/CAS semantics.
- [x] All generated revisions begin proposed; content cannot encode status or
  decision and acceptance never carries across revisions implicitly.
- [x] Public generated-proposal commands accept only a run identity and retrieve
  content/provenance through an injected verified-batch proof port; no raw
  generated content or caller-authored success path exists.
- [x] Direct authoring is a separate HUMAN-only revision path linked to an
  existing human interaction; SERVICE and MODEL cannot bypass run verification.
- [x] HUMAN may decide; MODEL is denied; SERVICE requires an injected policy and
  durable non-secret receipt.
- [x] Accepting a newer revision explicitly and atomically supersedes the named
  accepted predecessor; invalid transitions fail closed.
- [x] Projection views expose histories, pending review, accepted-by-kind, and
  framework/detail linkage without becoming a second state owner.

## Verification

- Event/codec/reducer/service/view, exact retry/conflict/race, authority,
  supersession, replay, and full gates.
