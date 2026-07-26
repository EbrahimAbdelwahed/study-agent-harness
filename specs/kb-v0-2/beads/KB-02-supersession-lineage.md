# KB-02: Source supersession and lineage

Status: Proposed
Risk: High
Depends On: KB-01
Parent coverage: §§4.2, 11–13, Appendix A.5

## Outcome

Current versus superseded revision state and explicit cross-source succession
are event-authorized, replayable, and visible without breaking historical
citations.

## API seam

- `source.superseded_by@1` event with trusted authority and strict source/revision
  bindings.
- Source lineage projection covering original bytes, substrate production,
  revisions, successors, and promoted study material.
- Read contracts report `current|superseded` and optional successor; they never
  migrate a citation automatically.

## Acceptance criteria

- [ ] A new revision of one source deterministically marks older revisions
  superseded while retaining their blobs and resolvability.
- [ ] Cross-source succession requires an explicit event and rejects cycles,
  self-links, missing endpoints, and conflicting successors.
- [ ] Default retrieval eligibility excludes superseded revisions but explicit
  historical reads remain possible.
- [ ] No timestamp or recency prior affects status or ranking.
- [ ] Lineage replays byte-identically and exposes the original blob chain.

## Verification

- Reducer/codec tests; cycle/conflict adversarial tests.
- Replay with same-source revision and new-edition cross-source succession.
- Compatibility tests for v0.1 source events.

## Out of scope

- Automatic cross-edition span alignment or substrate garbage collection.
