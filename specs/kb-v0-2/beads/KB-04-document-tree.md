# KB-04: Deterministic document tree

Status: Done — implemented and verified 2026-07-27
Risk: Medium
Depends On: KB-01
Parent coverage: §§8.1–8.3; M2

## Outcome

A frozen substrate deterministically projects into one bounded document tree
with stable paths, typed regions, spans, and uncertainty flags.

## API seam

- `TreeNode`, `NodeId`, `RegionKind`, `DialectProfile`, and `DocumentTree`
  immutable contracts in `study_agent.domain.tree`; `NodeId` is namespaced
  `node:sha256:<hex>` and derived from substrate, tree format version,
  declaring profile, and revision-local placement path only.
- Pure tree builder `study_agent.knowledge.tree.build_document_tree` consumes
  generic normalized text plus a connector-declared dialect profile. The
  profile is inert data (literal markers and booleans), so the builder imports
  no connector, performs no I/O, and calls no model.
- `TREE_FORMAT_VERSION` is the single format/version owner; bumping it changes
  every derived `node_id` and forces a rebuild.
- `node_id` is a structural handle only. It is never a citation or unit
  identity; KB-05 still owns `unit_id`.

## Acceptance criteria

- [x] Nodes are ordered, parent-linked, acyclic, and span-bounded.
- [x] Authored anchors win; deterministic derived slugs are fallback only.
- [x] Body, emphasis, summary, table, code, figure-ref, and item regions are
  represented without source-specific domain enums.
- [x] Flags propagate from typed regions to containing nodes.
- [x] Structure-poor input produces a valid root suitable for the v0.1 window
  fallback.
- [x] Same substrate/profile/version yields byte-identical tree projection.

## Verification

- Pure parser fixtures for Markdown, plain text, nested headings, duplicate
  headings, malformed islands, tables, callouts, and uncertainty markers:
  `tests/unit/knowledge/test_document_tree.py` (172 cases).
- Property tests over 60 seeded generated documents assert acyclicity, unique
  node ids, ordered non-overlapping siblings, parent containment, path
  extension, byte-identical rebuild, and descendant-flag containment.
- Import-boundary tests in `tests/architecture/test_knowledge_boundaries.py`
  keep `study_agent.knowledge` free of adapters, connectors, ingestion,
  providers, and filesystem access.
- `pytest` 2043 passed / 12 skipped, `ruff check` clean, strict `mypy` clean.

## Out of scope

- Creating retrievable units, indexing, connector I/O, or model parsing.
