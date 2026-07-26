# KB-10: Scope membership and corpus manifest

Status: Proposed
Risk: High
Depends On: KB-02, KB-05
Parent coverage: §§10.3, 12

## Outcome

Named scopes compose sources without duplication and expose a compact,
machine-readable manifest an agent can inspect before planning.

## API seam

- Event-authorized scope membership and versioned per-scope defaults.
- `CorpusManifest` read contract with sources/classes, counts, projection
  coverage, retrievers, adapter availability, conformance, and optional
  connector-declared “good at answering” hints when available.
- Scope policy supplies source-class priors, diversity caps, aliases, and
  fragment thresholds without tutoring behavior.

## Acceptance criteria

- [ ] A source can belong to many scopes without duplicating canonical units.
- [ ] Unknown/empty scopes and conflicting membership events fail explicitly.
- [ ] Manifest is deterministic, bounded, and exposes absence/degradation
  honestly.
- [ ] Unscoped whole-corpus search is explicit, never an accidental default.
- [ ] “Good at answering” comes only from connector manifests or trusted scope
  policy, never model inference.
- [ ] Scope policy contains no learner, tutor, scheduling, or workflow state.

## Verification

- Codec/reducer/replay tests for membership.
- Manifest snapshot tests with optional adapters absent/present.
- Multi-scope isolation and no-duplication integration tests.

## Out of scope

- Public transport/tool binding or agent planning.
