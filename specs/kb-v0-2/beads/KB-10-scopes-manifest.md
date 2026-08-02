# KB-10: Scope membership and corpus manifest

Status: Done — implemented and verified 2026-07-27; full suite has one sandbox-only browser bind failure
Risk: High
Depends On: KB-02, KB-05, KB-14
Parent coverage: §§10.3, 12

## Outcome

Named scopes compose sources without duplication and expose a compact,
machine-readable manifest an agent can inspect before planning.

## API seam

- Event-authorized scope membership and versioned per-scope defaults.
- `CorpusManifest` read contract with sources/classes, counts, projection
  coverage, retrievers, adapter availability, conformance, and declared
  “good at answering” hints.
- Scope policy supplies source-class priors, diversity caps, aliases, and
  fragment thresholds without tutoring behavior.

## Acceptance criteria

- [x] A source can belong to many scopes without duplicating canonical units.
- [x] Unknown/empty scopes and conflicting membership events fail explicitly.
- [x] Manifest is deterministic, bounded, and exposes absence/degradation
  honestly.
- [x] Unscoped whole-corpus search is explicit, never an accidental default.
- [x] “Good at answering” comes only from connector manifests or trusted scope
  policy, never model inference.
- [x] Scope policy contains no learner, tutor, scheduling, or workflow state.

## Verification

- Codec/reducer/replay tests for membership.
- Manifest snapshot tests with optional adapters absent/present.
- Multi-scope isolation and no-duplication integration tests.

## Out of scope

- Public transport/tool binding or agent planning.
