# KB-02: Source revision identity, selection, and lineage

Status: Done — implemented and verified 2026-07-27; one API-seam edge
deferred, see Deferred below
Risk: High
Depends On: KB-01
Parent coverage: §§4.2, 11–13, Appendix A.5

## Outcome

Current versus inactive revision selection and explicit cross-source succession
are event-authorized, replayable, and visible without breaking historical
citations.

## API seam

- Exact v0.2 revision-manifest fields, canonical encoding, and identity.
- `source.superseded_by@1` event with trusted authority and strict source/revision
  bindings.
- Source lineage projection covering original bytes, substrate production,
  revisions, and successors. Promoted study material is deferred (below).
- Read contracts report `current|inactive` and optional successor; they never
  migrate a citation automatically.

## Acceptance criteria

- [x] A new revision of one source can be selected while older revisions become
  inactive and retain their blobs and resolvability.
- [x] Cross-source succession requires an explicit event and rejects cycles,
  self-links, missing endpoints, and conflicting successors.
- [x] Default retrieval eligibility excludes inactive revisions but explicit
  historical reads remain possible.
- [x] No timestamp or recency prior affects status or ranking.
- [x] Lineage replays byte-identically and exposes the original blob chain.

## Verification

- `tests/unit/knowledge/test_succession_lineage.py` (17 cases): reducer/codec
  round-trip, service-authority and forged-identity rejection, and adversarial
  self-link, missing-endpoint, conflicting-successor, and cycle cases.
- Replay covers a same-source second revision and a new-edition cross-source
  succession; lineage encoding is asserted timestamp-free.
- v0.1 source events keep their payload and append behavior: the succession
  event is additive and the existing suite is unchanged.
- `pytest` 2060 passed / 12 skipped, `ruff check` clean, strict `mypy` clean.

## Decisions for review

- `revision_id` keeps its existing v0.1 derivation. ADR-0014 assigns the v0.2
  field set and canonical encoding to this bead, and both are now defined by
  `RevisionManifest.to_json`, but minting a second revision identity would
  contradict the ADR's rule that v0.2 adds versioned successors instead of
  mutating persisted contracts. A reviewer should confirm this reading before
  KB-03 and KB-16 bind to it.
- Selection reuses the existing `source.revision_selected@1` event and the
  `current_revision_id` projection field; this bead adds only the read
  contract on top. No second selection authority was introduced.
- Succession edges are stored as an append-ordered array rather than a map
  keyed by a composite string, so no separator can ever be ambiguous inside a
  source or revision identifier.

## Deferred

- The lineage projection does not yet expose promoted study material. That
  edge requires reading the artifacts projection, whose ownership ADR-0014
  does not assign to ingestion, and KB-13 owns the agent-facing read surface.
  It is intentionally left to KB-13 rather than creating a cross-package
  coupling here.

## Out of scope

- Automatic cross-edition span alignment or substrate garbage collection.
