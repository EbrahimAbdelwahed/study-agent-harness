# Task Bead: TUT-04E2 artifact replay and export v2

Status: Blocked on TUT-04B
Priority: P0
Type: contract
Depends On: TUT-04B

## Outcome

Artifact histories replay in runtime composition roots and export through an
explicit deterministic v2 without mutating export v1.

## Acceptance Criteria

- [ ] CLI/lifecycle/export-v2 registries include exact artifact schemas and old
  repositories replay unchanged.
- [ ] Export v1 golden bytes and file set remain byte-identical for pre-artifact
  repositories; artifact-aware export requires explicit v2.
- [ ] Requesting v1 for an artifact-bearing stream fails with the stable
  `artifact export requires v2` error and never silently omits artifact events.
- [ ] V2 retains content, lineage, status, decisions, source commitments, profile
  selection, and public version/fingerprint provenance.
- [ ] V2 excludes credentials, principal IDs, idempotency keys, raw prompts,
  model response IDs/usage, private policy internals, and unverified media.

## Verification

- Old-repository replay, v1 golden non-regression, artifact-bearing-v1
  fail-closed, deterministic v2 roundtrip, source linkage, hostile-secret
  redaction, and full gates.
