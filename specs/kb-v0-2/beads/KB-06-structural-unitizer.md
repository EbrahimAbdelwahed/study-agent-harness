# KB-06: Structural unitizer and granularity ladder

Status: Proposed
Risk: Medium
Depends On: KB-05
Parent coverage: §§5.1–5.2, 8.2; M2

## Outcome

One deterministic unitizer emits document/section/passage levels without
crossing tree boundaries and preserves the v0.1 1,200-character floor for
structure-poor input.

## API seam

- Pure `UnitizerPolicy` and `UnitDraft` seam owned by the KB unitizer.
- Connector profiles may identify regions but cannot derive final unit IDs.
- Explicit unitizer version and migration/remap report.

## Acceptance criteria

- [ ] Small sections emit a section and passage unit at their declared levels.
- [ ] Large sections split only inside the node at paragraph boundaries.
- [ ] Tables, emphasis regions, and code fences are atomic and never split.
- [ ] No emitted span overlaps improperly, escapes its tree node, or omits
  canonical text unintentionally.
- [ ] Structure-poor input matches the frozen v0.1 window behavior.
- [ ] Version change yields a complete remap report and never guesses an
  unmatched citation.

## Verification

- Golden unitization fixtures and deterministic ID checks.
- Boundary/property tests for exact cap, oversized paragraphs, empty nodes,
  Unicode, tables, and nested regions.
- v0.1 fallback compatibility fixture.

## Out of scope

- Fragment signal scoring, connectors, or indexing.
