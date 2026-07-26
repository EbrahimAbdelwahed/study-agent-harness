# KB-05: Uniform retrievable unit contracts and projection

Status: Proposed
Risk: High
Depends On: KB-00, KB-01, KB-04
Parent coverage: §§4–5.3, 8, 11; M2

## Outcome

Every indexable text, figure, table, fragment, and exam item shares one strict
provider-neutral unit shape and one replayable projected owner.

## API seam

- Closed `UnitKind`, granularity, `CanonicalRef`, `UnitMeta`, `UnitLinks`,
  `UnitSignal`, and `RetrievableUnit` contracts.
- Identity and placement fields follow the accepted KB-00 ADR.
- Unit projection consumes canonical events/tree outputs; adapters cannot write
  authoritative unit rows directly.

## Acceptance criteria

- [ ] One row shape represents all declared kinds without source-specific
  branches.
- [ ] Text units reference substrate spans; figures reference blobs; neither
  duplicates canonical content in the unit.
- [ ] Links are bounded, typed, cycle-checked where required, and reference
  known units or explicit provisional targets.
- [ ] Flags, source class/role/trust, review status, ordinal, page hint, and
  language survive replay.
- [ ] Invalid identities, refs, granularity/kind combinations, or links reject
  before projection.
- [ ] Existing v0.1 retrieval consumers have a documented migration seam.

## Verification

- Contract/codec tests and hostile malformed payload corpus.
- Replay and projection-corruption tests.
- Architecture test proving no connector/index owns a parallel unit type.

## Out of scope

- Unit boundary algorithms, scoring, projections, or public search.
