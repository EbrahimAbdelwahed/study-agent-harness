# KB-22A: Embedding and vector-retrieval adapters

Status: Proposed — dependency decision required
Risk: High
Depends On: KB-08, KB-11, KB-16
Parent: KB-22

## Outcome

Provider-neutral embeddings and optional vector indexes register
`vec_projection`, `vec_canonical`, and later `vec_figure` without changing
callers or the offline lexical path.

## Acceptance criteria

- [ ] Embedding identity binds projection/canonical input hash, model identity,
  dimensions, adapter version, and configuration.
- [ ] Dimension/model mismatch, partial batches, malformed vectors, NaN/Inf,
  stale cache, timeout, and rate limit failures are typed and isolated.
- [ ] Brute-force reference behavior is pinned before optional sqlite-vec
  selection; dependency/license/platform overhead receives explicit approval.
- [ ] Vector candidates conform to KB-11 and cannot create evidence.
- [ ] Missing provider/key/index only removes vector lists.
- [ ] Direct image embeddings remain excluded absent a new measured-gap bead.

## Verification

- Scripted provider/vector conformance tests, optional-install CI, cache
  invalidation, batch recovery, and security review.
- Retrieval eval delta against the exact offline baseline.

## Out of scope

- Reranking, model projection, or provider-specific public contracts.
