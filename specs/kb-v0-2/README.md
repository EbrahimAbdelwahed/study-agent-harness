# Knowledge Base v0.2 implementation beads

Status: Active — KB-00 through KB-05 complete; KB-06, KB-07, KB-08, and
KB-14 dependency-ready
Last updated: 2026-07-27
Parent spec: [`../../docs/specs/kb-v0-2-retrieval-architecture.md`](../../docs/specs/kb-v0-2-retrieval-architecture.md)

## Next Agent Prompt

Read ADR-0014, the parent spec, and either
[KB-03](beads/KB-03-citation-v2-verification.md) or
[KB-05](beads/KB-05-uniform-retrievable-units.md). These are the two
independent dependency-ready continuations now that the canonical substrate
tracer, supersession/lineage, and the deterministic document tree are in
place. Preserve v0.1
ingestion and retrieval behavior through versioned successors and explicit
migration tests; do not add model, vector, OCR, vision, transport, UI, or
tutor behavior to the offline trunk. Before ending a pass, update this
section, the owning bead status, and the checklist below.

Current pickup: KB-06 structural unitizer, KB-07 typed fragments, KB-08
projection core, and KB-14 connector protocol. All four are independent.

Active blockers: none. Owner decisions are recorded in
[`answers.md`](../../docs/decision-requests/20260727-kb-v0-2-completion/answers.md).

KB-06 and KB-13 both depend on the caller obligation KB-03 records: a
`RetrievableUnit` handed to the citation verifier must come from the canonical
registry, never from connector or model input.

KB-06 must feed `reduce_units` real `RevisionBinding` values read from
canonical projection state; the binding gate is the only thing standing
between a unitizer bug and forged evidence, because ADR-0014 keeps
`source_id` and the substrate out of `unit_id`.

Open for review: KB-02 deliberately kept the existing v0.1 `revision_id`
derivation instead of minting a second revision identity, and deferred the
promoted-study-material edge of the lineage projection to KB-13. Confirm both
before KB-03 and KB-16 bind to them.

KB-05 must consume `study_agent.domain.tree` and must not re-derive structure:
`node_id` is a structural handle, never a unit or citation identity, and
`TREE_FORMAT_VERSION` is the only tree format owner.

## Goal

Deliver a source-, model-, and agent-agnostic knowledge base whose canonical
evidence remains immutable and mechanically verifiable while every index and
derived artifact is replaceable. The lexical path must remain fully useful
offline with no keys, network, model, vector, OCR, or vision dependency.

## One-owner architecture

- Existing `BlobStore` remains the sole content-addressed byte owner.
- The event stream remains the sole canonical mutation authority.
- One substrate owner defines frozen normalized text and page maps.
- One unitizer owns revision-local `RetrievableUnit` occurrence creation and
  identity; connectors translate source dialects into bounded drafts.
- One citation verifier resolves text and figure evidence from canonical bytes.
- One projection owner defines searchable handles; indexes only consume it.
- One retriever registry owns candidate discovery; fusion never enumerates
  concrete retrievers.
- SQLite remains an adapter for discardable operational state, never domain
  truth.
- Optional OCR, vision, vector, reranker, and model projectors plug into ports;
  their absence cannot change correctness or availability.

No bead may introduce a compatibility wrapper without naming its removal
condition. Unshipped v0.2 scaffolding migrates directly to the final owner.

## Delivery stages

1. **Architecture gate:** KB-00.
2. **Canonical evidence spine:** KB-01 through KB-03.
3. **Structural corpus model:** KB-04 through KB-08.
4. **Source extension:** KB-14 and KB-15.
5. **Offline retrieval surface:** KB-09 through KB-13.
6. **Incremental offline baseline:** KB-16.
7. **Rich study material:** KB-17 through KB-21.
8. **Optional semantic quality:** KB-22.
9. **Release evidence:** KB-23.

The first materially useful checkpoint is KB-09B: structure-aware lexical
search over projection, terms, and canonical text. The complete offline
baseline is KB-16. Figures and semantic adapters remain independently
droppable after that point.

## Dependency graph

```text
KB-00 architecture closure
  └─ KB-01 substrate contracts/events
      ├─ KB-02 supersession and lineage
      │   └─ KB-03 citation verification (also requires KB-01)
      └─ KB-04 document tree
          └─ KB-05 uniform units
              ├─ KB-06 structural unitizer
              │   └─ KB-07 typed fragments
              ├─ KB-08 projection core
              │   └─ KB-09A lexical projector
              │       └─ KB-09B SQLite lexical surfaces
              └─ KB-14 connector protocol
                  ├─ KB-15A Markdown/notes connectors
                  ├─ KB-15B PDF profile
                  └─ KB-15C study-material/doctor (also requires KB-15A)

KB-02 + KB-05 ───────────> KB-10 scopes and manifest
KB-09B + KB-10 ─────────> KB-11 retriever registry
KB-05 + KB-07 + KB-11 ──> KB-12 fusion pipeline
KB-03 + KB-04 + KB-10 + KB-12 ──> KB-13 agent primitives
KB-02 + KB-05 + KB-08 + KB-09B ──> KB-16 incrementality

KB-03 + KB-05 + KB-14 + KB-16 ──> KB-17A figure units/structural anchors
KB-15B + KB-17A ─────────────────> KB-17B derived PDF anchors
KB-02 + KB-17A + KB-17B ─────────> KB-17C review/correspondence
KB-12 + KB-13 + KB-17C ─────────> KB-18 figure retrieval
KB-05 + KB-12 + KB-14 ──────────> KB-19 exam items/link graph
KB-17C + KB-18 ─────────────────> KB-20 OCR labels
KB-18 + KB-20 ──────────────────> KB-21 figure cards/surrogates
KB-08 + KB-11 + KB-16 ──────────> KB-22A embedding/vector adapters
KB-12 + KB-16 ──────────────────> KB-22B reranker adapter
KB-08 + KB-16 ──────────────────> KB-22C model projector
KB-13 + KB-16 + KB-18 + KB-19 ──> KB-23 release evals
KB-20, KB-21, and KB-22A/B/C are optional inputs to KB-23 adapter-specific gates.
```

## Global invariants

- Canonical events and blobs are append-only; projections and indexes rebuild.
- Canonical citations never target generated summaries, handles, embeddings,
  OCR text, figure cards, or surrogates.
- A result always carries flags, selection status, explicit succession,
  retriever provenance, and
  projection provenance.
- Literal query compilation remains injection-safe and model-free.
- Supersession is structural; no recency score is introduced.
- Cross-document figure anchors require a declared correspondence.
- Reviewed figure anchors survive extractor reruns.
- Structural conformance findings may degrade unitization; admission failures
  for malformed bytes, forged IDs, invalid spans, unsafe paths, unsupported
  media, and integrity failures still reject.
- Default tests are offline and credential-free.
- External dependencies require a separate adapter/dependency decision and
  their own CI lane.

## Risk policy

- **High:** public contracts, event/schema changes, persistence, identity,
  citation integrity, external adapters. Use plan → plan review →
  implementation → code/security review as applicable → independent tests.
- **Medium:** deterministic algorithms and bounded new projections. Use a short
  plan, focused implementation/tests, and one semantic review.
- **Low:** additive registration, documentation, and mechanical wiring. Use
  direct implementation, diff self-review, and focused tests.

## Global TODO

- [x] [KB-00 architecture closure](beads/KB-00-architecture-closure.md)
- [x] [KB-01 canonical substrate](beads/KB-01-canonical-substrate.md)
- [x] [KB-02 supersession and lineage](beads/KB-02-supersession-lineage.md)
- [x] [KB-03 citation v2 verification](beads/KB-03-citation-v2-verification.md)
- [x] [KB-04 document tree](beads/KB-04-document-tree.md)
- [x] [KB-05 uniform retrievable units](beads/KB-05-uniform-retrievable-units.md)
- [ ] [KB-06 structural unitizer](beads/KB-06-structural-unitizer.md)
- [ ] [KB-07 typed fragments and promotion](beads/KB-07-typed-fragments.md)
- [ ] [KB-08 projection core](beads/KB-08-projection-core.md)
- [ ] [KB-09 lexical projection and indexes parent](beads/KB-09-lexical-projection-indexes.md)
  - [ ] [KB-09A lexical projector](beads/KB-09A-lexical-projector.md)
  - [ ] [KB-09B SQLite lexical surfaces](beads/KB-09B-sqlite-lexical-surfaces.md)
- [ ] [KB-10 scopes and manifest](beads/KB-10-scopes-manifest.md)
- [ ] [KB-11 retriever registry](beads/KB-11-retriever-registry.md)
- [ ] [KB-12 fusion pipeline](beads/KB-12-fusion-pipeline.md)
- [ ] [KB-13 agent-facing primitives](beads/KB-13-agent-primitives.md)
- [ ] [KB-14 connector protocol](beads/KB-14-connector-protocol.md)
- [ ] [KB-15 baseline connectors parent](beads/KB-15-baseline-connectors.md)
  - [ ] [KB-15A Markdown and notes](beads/KB-15A-markdown-notes-connectors.md)
  - [ ] [KB-15B PDF profile](beads/KB-15B-pdf-connector-profile.md)
  - [ ] [KB-15C study material and doctor](beads/KB-15C-study-material-profile-doctor.md)
- [ ] [KB-16 incremental maintenance](beads/KB-16-incremental-maintenance.md)
- [ ] [KB-17 figure state and anchors parent](beads/KB-17-figure-state-anchors.md)
  - [ ] [KB-17A figure units and structural anchors](beads/KB-17A-figure-units-structural-anchors.md)
  - [ ] [KB-17B derived PDF anchors](beads/KB-17B-derived-pdf-anchors.md)
  - [ ] [KB-17C review and correspondence](beads/KB-17C-anchor-review-correspondence.md)
- [ ] [KB-18 figure retrieval](beads/KB-18-figure-retrieval.md)
- [ ] [KB-19 exam items and link graph](beads/KB-19-exam-items-link-graph.md)
- [ ] [KB-20 OCR figure labels](beads/KB-20-ocr-figure-labels.md)
- [ ] [KB-21 figure cards and surrogates](beads/KB-21-figure-derived-artifacts.md)
- [ ] [KB-22 semantic adapters parent](beads/KB-22-semantic-adapters.md)
  - [ ] [KB-22A embedding/vector adapters](beads/KB-22A-embedding-vector-adapters.md)
  - [ ] [KB-22B reranker adapter](beads/KB-22B-reranker-adapter.md)
  - [ ] [KB-22C model projector](beads/KB-22C-model-projector.md)
- [ ] [KB-23 release evals and closure](beads/KB-23-release-evals.md)

## Scope firewall

Out of scope for every bead unless the parent spec is amended: tutoring policy,
spaced repetition, planner/synthesis behavior, UI, HTTP/MCP, agent SDK binding,
PDF converter internals, transcription internals, image generation, print
layout, automatic cross-edition citation migration, and a hosted database.

## Human review map

- KB-00: approve identity, compatibility, conformance, and replay semantics.
- KB-05: `node_id` still does not commit to `span`. Inside
  `build_document_tree` this is safe, and README keeps `node_id` a structural
  handle, but before KB-08 trusts a persisted tree span for anything
  evidentiary either bind `span` into `node_id` or add a tree admission
  function that re-derives against the substrate.
- KB-09B: inspect retrieval quality on fixed medical fixtures.
- KB-15C: inspect real-semester conformance output before tuning profiles.
- KB-17C: approve figure-anchor event and review authority.
- KB-20/21/22: approve each external dependency/provider decision separately.
- KB-23: accept release only from measured eval deltas and green CI.
