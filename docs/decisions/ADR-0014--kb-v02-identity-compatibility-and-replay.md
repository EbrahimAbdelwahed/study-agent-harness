# ADR-0014: KB v0.2 identity, compatibility, and replay

Date: 2026-07-26
Status: Accepted

## Context

The proposed KB v0.2 architecture coupled revision-local placement to reusable
derived work. Its `unit_id` included `revision_id` and canonical offsets while
also claiming unchanged units would retain that identity across revisions.
The proposal also described every derived artifact as deletable while requiring
byte-identical replay after deletion, and treated every connector finding as
non-blocking even when canonical integrity was invalid.

The existing v0.1 `Citation`, `SourceChunk`, source events, retrieval ports, and
exports are strict persisted contracts used throughout the harness. Mutating
them in place would make old event streams and exports ambiguous.

## Decision

### Identity and collision domains

- `revision_id` identifies one immutable revision manifest. Its exact v0.2
  field set and canonical encoding are owned by KB-02 after KB-01 freezes the
  substrate receipt contract. KB-01 must not invent or replace revision
  identity. Unitizer and projector versions remain excluded.
- `substrate_id` is namespaced as `substrate:sha256:<lowercase hex>`, where the
  digest covers the exact frozen normalized UTF-8 bytes and no metadata.
- `substrate_production_id` is namespaced as
  `substrate-production:sha256:<lowercase hex>`. Its digest hashes the
  repository's strict canonical JSON
  encoding of source identity, trusted original blob binding, substrate
  identity, converter name/version, normalization version, page-map contract,
  page-map policy version, and admission-policy version under the
  `study-agent/substrate-production/v1` domain separator. `produced_at` is not
  identity-bearing; an exact retry retains the first committed timestamp.

The page-map JSON contract is an ordered array of closed objects with exactly
`offset` and `page` integer fields. The production identity object uses exactly
`source_id`, `original_blob`, `substrate_id`, `converter_name`,
`converter_version`, `normalization_version`, `page_map_policy_version`,
`page_count`, `page_map`, and `admission_policy_version`.
- `unit_id` identifies one revision-local occurrence. It commits to revision,
  unit kind, granularity, canonical reference, placement key, and unitizer
  version. Duplicate passages therefore remain distinct.
- `lineage_key` is an optional cross-revision navigation key derived from a
  stable authored anchor. It is never citation identity or mutation authority.
- `projection_input_fingerprint` commits to exact canonical input bytes plus
  effective structural context, flags, supplied scope policy, and producer
  policy. It is the cross-revision cache-reuse key.
- `projection_id` commits to the unit occurrence, input fingerprint, opaque
  producer identity/version, and exact output hash.
- `TextCitationV2` commits to source, revision, unit occurrence, substrate,
  Unicode-code-point half-open span, and the SHA-256 of the quoted UTF-8 bytes.
  Locator and page values remain non-identifying hints.
- `FigureCitationV1` commits to the exact figure blob hash. Anchors and origin
  pages remain links or hints.

### Compatibility

v0.2 adds versioned successors rather than mutating v0.1 contracts:
`TextCitationV2`, `FigureCitationV1`, `EvidencePacketV2`, and
`KnowledgeBasePortV2`. Existing v0.1 events and exports remain readable.
Legacy `source.revision_ingested@1` data maps deterministically to a legacy
substrate and legacy passage occurrences; events are never rewritten.

Built-in consumers migrate at KB-13. The runtime v1 FTS bridge is removed by
KB-16 and verified absent at KB-23. Legacy codecs and citation resolution stay
available permanently so historical exports and events remain verifiable.

### Selection and succession

Current revision selection is reversible and is distinct from succession.
Reads expose `selection_status: current | inactive` plus explicit successor
relations. Default retrieval uses current revisions. Historical citations
resolve regardless of selection. No timestamp or recency score participates.

### Replay

- Canonical event projections replay byte-identically for the same event
  schemas and reducers.
- Deterministic tree, unit, and offline projection outputs reproduce
  byte-identically for pinned inputs, algorithms, and configuration.
- A model/tool artifact is exact only while its content-addressed output blob
  is retained. After deletion, regeneration produces a new artifact and
  receipt with equivalent schema and lineage, not a promise of identical
  bytes.
- Cache validity follows fingerprints. Cache invalidation and rebuild audit are
  operational state, not canonical domain events.

### Admission and conformance

`source.substrate_produced@1` is service-authorized. Its application seam
accepts only source-bound host receipts for both original and converter output;
human/model execution contexts and unbound raw blob references cannot author
converter or policy provenance.

`ConformanceFinding` describes non-blocking structural quality and may select a
weaker deterministic fallback. `AdmissionFailure` blocks unsafe or unsupported
media, size/path violations, invalid UTF-8, forged identities or hashes,
malformed schemas, corrupt blobs, invalid spans, and invalid converter/page-map
provenance.

### Ownership

- Existing `BlobStore` remains the only byte owner.
- Existing ingestion owns source revisions and evolves to own substrates.
- `study_agent.domain` owns provider-neutral v2 values.
- `study_agent.knowledge` owns pure trees, unitization, projection selection,
  registry/fusion, and compatibility mapping.
- `study_agent.ports.knowledge` exposes `KnowledgeBasePortV2`.
- SQLite adapters own discardable indexes and sync state only.
- Connectors emit bounded generic drafts. They do not create final identities,
  indexes, scorers, results, prompts, or provider behavior.
- Linguistic/model behavior remains in versioned skills and playbooks behind
  generic worker/model ports; provider adapters remain technical.

The canonical unit occurrence contains only identity, source/revision, kind,
granularity, canonical reference, structural path, immutable metadata, and
flags. Projection assignments, typed derived relations, per-scope index
eligibility, and operational signals are separate projections.

Typed fragment occurrences are materialized once. Per-scope promotion controls
index eligibility and never changes unit identity.

## Consequences

- Inserting preceding text changes placement and citation offsets but does not
  prevent safe reuse when the exact projection input fingerprint is unchanged.
- Identical passages at different placements never collapse accidentally.
- v0.1 remains usable during migration without an indefinite second runtime
  retrieval implementation.
- Deleting paid/model artifacts no longer creates an impossible byte-replay
  promise.
- Connector quality degradation remains permissive without weakening canonical
  integrity.

## Alternatives Considered

- Content-only stable unit IDs: rejected because duplicate placements and
  citation/link targets become ambiguous.
- Authored-anchor-only identity: rejected because structure-poor sources lack
  anchors and content changes could retain a misleading identity.
- Mutating v0.1 contracts in place: rejected because persisted strict envelopes
  and exports would change meaning.
- Canonical cache-invalidation events: rejected because operational cache state
  would become domain truth.
- Model/OCR logic inside connectors: rejected because it violates the offline
  trunk and the behavior/adapter boundary.
