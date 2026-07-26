# KB-22B: Optional reranker adapter

Status: Proposed — provider decision required
Risk: High
Depends On: KB-12, KB-16
Parent: KB-22

## Outcome

A bounded provider-neutral reranker may reorder already fused candidates but
cannot add evidence, widen scope, or bypass canonical resolution.

## Acceptance criteria

- [ ] Input is a capped deterministic candidate set with opaque IDs and bounded
  text/context chosen by trusted policy.
- [ ] Output is an exact permutation/subset with scores/provenance; unknown,
  duplicate, missing, or invented candidates fail closed.
- [ ] Timeout/rate/provider failure returns the original fused order explicitly.
- [ ] No reranker result is canonical or citable.
- [ ] Model/provider identity, prompt/config version, input fingerprint, and
  output are cache-keyed and auditable.
- [ ] Default weight/use requires measured precision gain without citation loss.

## Verification

- Scripted provider, malformed permutation, injection, timeout, fallback,
  idempotency, and provenance tests.
- Precision@k eval against unchanged fused candidates.

## Out of scope

- Candidate discovery, evidence synthesis, or mandatory reranking.
