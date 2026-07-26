# KB-00: Architecture closure and v0.1 compatibility

Status: Done — ADR-0014 accepted 2026-07-26
Risk: High
Depends On: none
Parent coverage: §§3–5.3, 6.1, 11, 13–17

## Outcome

An accepted ADR makes the v0.2 identity, migration, conformance, replay, and
ownership contracts internally consistent before a public schema is written.

## Contract to close

- Decide how unchanged logical units retain reusable identity across revisions
  even though current `unit_id` derivation includes `revision_id` and
  `canonical_ref`.
- Pin the relationship among source revision, revision-local placement,
  stable/content identity, projection cache identity, and citation identity.
- Separate non-blocking structural conformance findings from blocking safety,
  schema, corruption, and integrity failures.
- Define byte-identical replay for deterministic projections and exact replay
  versus regeneration for model/tool artifacts.
- Map every existing v0.1 ingestion, `Citation`, `SourceContentPort`,
  `RetrievalPort`, FTS, CLI, export, and event consumer to its v0.2 owner.
- Decide whether an existing public contract evolves in place or receives a
  versioned successor; no indefinite dual model.

## Acceptance criteria

- [x] The ADR resolves all three listed contradictions without hand-waving.
- [x] Every identity has a canonical derivation and collision domain.
- [x] Existing v0.1 events and exports remain readable and their migration
  behavior is explicit.
- [x] One owner is named for substrate, units, citations, projections,
  connectors, registry, and operational sync.
- [x] Any compatibility bridge has an owner, removal condition, and removal
  bead.
- [x] The parent spec and bead graph are corrected if the accepted decision
  changes dependencies.

## Verification

- Architecture review against actual v0.1 consumers and fixtures.
- Adversarial examples: edited heading, inserted preceding text, unchanged
  section in changed revision, duplicate passage, reconversion, deleted model
  cache, and malformed-but-readable document.

## Out of scope

- Runtime implementation or choosing vector/OCR/model dependencies.

## Closure

ADR-0014 resolves occurrence versus reuse identity, versioned v0.1
compatibility, selection versus succession, deterministic versus regenerated
replay, admission versus conformance, and one-owner package boundaries. KB-01
is the next dependency-ready bead.
