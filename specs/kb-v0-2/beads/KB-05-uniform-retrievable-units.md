# KB-05: Uniform retrievable unit contracts and projection

Status: Done — implemented, reviewed, and verified 2026-07-27
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

- [x] One row shape represents all declared kinds without source-specific
  branches.
- [x] Text units reference substrate spans; figures reference blobs; neither
  duplicates canonical content in the unit.
- [x] Links are bounded, typed, cycle-checked where required, and reference
  known units or explicit provisional targets.
- [x] Flags, source class/role/trust, review status, ordinal, page hint, and
  language survive replay.
- [x] Invalid identities, refs, granularity/kind combinations, or links reject
  before projection.
- [x] Existing v0.1 retrieval consumers have a documented migration seam.

## Verification

- `tests/unit/knowledge/test_retrievable_units.py` (54 cases): contract/codec
  round-trip for every kind, hostile malformed payload corpus, replay and
  projection-corruption cases, link integrity and parent-cycle rejection,
  binding-gate rejection, and the v0.1 chunk migration seam.
- `tests/architecture/test_knowledge_boundaries.py` proves no module outside
  `study_agent.domain.units` defines a parallel unit type, by AST class-name
  scan over the whole package.
- `pytest` 2116 passed / 12 skipped, `ruff check` clean, strict `mypy` clean.

## Review outcome

Reviewed by an independent code-review and an independent security-review
pass. Both raised findings against this bead; all were fixed before closure:

- Links had no referential integrity and no cross-unit cycle check, which is
  the literal text of an acceptance criterion. `reduce_units` now validates
  the whole batch transactionally before writing any row.
- `admit()` proved only self-consistency of the hash. Because ADR-0014
  deliberately excludes `source_id` and the substrate from `unit_id`, a unit
  naming a real span under the wrong source, or naming a revision that was
  never ingested, was admissible. `reduce_units` now requires the caller to
  supply `RevisionBinding` values and checks source ownership, substrate
  binding, and span bounds against them.
- Free-text fields (`provisional_target`, `flags`, `role`, `source_class`,
  `language`, path segments) were unbounded and could smuggle a paragraph of
  canonical text past the "units never carry text" invariant. All are now
  capped at 128 characters.
- Dead `granularity_for` export removed.

## Out of scope

- Unit boundary algorithms, scoring, projections, or public search.
