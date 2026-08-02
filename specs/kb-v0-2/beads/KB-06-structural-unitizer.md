# KB-06: Structural unitizer and granularity ladder

Status: Done — implemented and verified 2026-07-27
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

- [x] Small sections emit a section and passage unit at their declared levels.
- [x] Large sections split only inside the node at paragraph boundaries.
- [x] Tables, emphasis regions, and code fences are atomic and never split.
- [x] No emitted span overlaps improperly, escapes its tree node, or omits
  canonical text unintentionally.
- [x] Structure-poor input matches the frozen v0.1 window behavior.
- [x] Version change yields a complete remap report and never guesses an
  unmatched citation.

## Verification

- Golden unitization fixtures and deterministic ID checks in
  `tests/unit/knowledge/test_unitizer.py`.
- Boundary/property tests for exact cap, oversized paragraphs, empty nodes,
  Unicode, tables, and nested regions.
- v0.1 fallback compatibility fixture.

## Out of scope

- Fragment signal scoring, connectors, or indexing.
