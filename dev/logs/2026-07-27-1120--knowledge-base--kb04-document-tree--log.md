# Log: KB-04 deterministic document tree

Date: 2026-07-27 11:20
Area: knowledge-base

## Summary

Implemented KB-04. A frozen substrate now projects deterministically into one
bounded, acyclic document tree with stable placement paths, generic typed
regions, code-point spans, and propagated uncertainty flags. The builder is
pure: no I/O, no connector import, no model call.

Contracts live in `study_agent.domain.tree`; the builder lives in the new
`study_agent.knowledge` package, matching the ownership ADR-0014 assigns
("`study_agent.knowledge` owns pure trees").

## Files Changed

- `src/study_agent/domain/tree.py`: new `RegionKind`, `HeadingSyntax`,
  `DialectProfile`, `TreeNode`, `DocumentTree`, `MALFORMED_FLAG`, plus
  single-root/acyclic/ordered/contained structural validation.
- `src/study_agent/domain/identifiers.py`: added `NodeId` (`node:sha256:<hex>`)
  and `node_id_for`, domain-separated `study-agent/document-tree-node/v1`.
- `src/study_agent/domain/__init__.py`: additive exports only.
- `src/study_agent/knowledge/__init__.py`, `src/study_agent/knowledge/tree.py`:
  new package and pure builder with `TREE_FORMAT_VERSION`.
- `tests/unit/knowledge/test_document_tree.py`: new (172 cases).
- `tests/architecture/test_knowledge_boundaries.py`: extended for
  `domain/tree.py` and the whole `knowledge` package.
- `specs/kb-v0-2/beads/KB-04-document-tree.md`, `specs/kb-v0-2/README.md`.

## Decisions

- `node_id` commits to substrate, tree format version, declaring profile, and
  revision-local placement path — never to node text, so an unchanged
  structure rebuilds byte-identically. It is a structural handle only; KB-05
  still owns `unit_id`.
- A `DialectProfile` is inert data (literal marker strings plus booleans). The
  builder therefore never imports a connector and no source-specific domain
  vocabulary can reach the structural trunk.
- Flags are `frozenset[str]` of markers declared by the profile, per §8.1;
  undeclared markers are ignored rather than guessed.
- Sibling path segments are deduplicated in document order across headings and
  regions together, so a heading slugged `table-1` cannot collide with a table
  region segment.

## Verification

- `pytest`: 2043 passed, 12 skipped (baseline before this change: 1869 passed,
  12 skipped).
- `ruff check .`: clean. Strict `mypy`: clean, 486 source files.
- Property tests over 60 seeded generated documents assert acyclicity, unique
  node ids, ordered non-overlapping siblings, parent containment, path
  extension, byte-identical rebuild, and descendant-flag containment.

## Notes

- Two real defects were caught by the property tests during implementation and
  fixed: a merged region (callout/table) escaped across a fenced code block and
  produced overlapping siblings, and multi-line callout continuations were
  dropped so a flag inside a callout body never reached its region.
- No dependency was added. Property tests are seeded `random` over a fixed
  block corpus rather than Hypothesis, because a new dev dependency needs its
  own decision under ADR policy.
- KB-02 was left open; see the handoff note in the session report. Nothing in
  this change touches revision identity, selection, or supersession.
