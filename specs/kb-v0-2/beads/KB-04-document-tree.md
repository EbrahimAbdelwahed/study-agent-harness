# KB-04: Deterministic document tree

Status: Proposed
Risk: Medium
Depends On: KB-01
Parent coverage: §§8.1–8.3; M2

## Outcome

A frozen substrate deterministically projects into one bounded document tree
with stable paths, typed regions, spans, and uncertainty flags.

## API seam

- `TreeNode`, `NodeId`, `RegionKind`, and `DocumentTree` immutable contracts.
- Pure tree builder consumes generic normalized text plus a connector-produced
  dialect profile; it does not import connector implementations.
- Tree projection is rebuildable and has one format/version owner.

## Acceptance criteria

- [ ] Nodes are ordered, parent-linked, acyclic, and span-bounded.
- [ ] Authored anchors win; deterministic derived slugs are fallback only.
- [ ] Body, emphasis, summary, table, code, figure-ref, and item regions are
  represented without source-specific domain enums.
- [ ] Flags propagate from typed regions to containing nodes.
- [ ] Structure-poor input produces a valid root suitable for the v0.1 window
  fallback.
- [ ] Same substrate/profile/version yields byte-identical tree projection.

## Verification

- Pure parser fixtures for Markdown, plain text, nested headings, duplicate
  headings, malformed islands, tables, callouts, and uncertainty markers.
- Property tests for acyclicity, ordered spans, and containment.

## Out of scope

- Creating retrievable units, indexing, connector I/O, or model parsing.
