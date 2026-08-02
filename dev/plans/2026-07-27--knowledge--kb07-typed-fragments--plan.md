# Plan: KB-07 typed fragments and promotion gate

Date: 2026-07-27
Area: knowledge base

## Goal

Expose deterministic, model-free typed fragment drafts from an admitted
document tree and a bounded per-scope promotion policy.  Promoted fragments
must remain revision-local canonical units owned by the existing KB-06
unitizer and KB-05 admission path.

## Scope

- In scope: immutable fragment contracts, tree-region extraction, four-signal
  promotion decisions, bounded policy validation, and the small unitizer seam
  needed to pass promoted drafts through the existing identity owner.
- Out of scope: retrieval/indexes, persistence/events, providers/models,
  tutoring behavior, scope membership, and new dependencies.

## Approach

1. Add strict `FragmentKind`, `FragmentDraft`, signal, policy, and decision
   values with deterministic canonical encodings.
2. Re-derive/validate tree context before extracting only supported typed
   regions; preserve substrate, source, revision, node/path, span, and flags.
3. Compute independent length, structural, IDF rarity, and explicit-reference
   signals; normalize weighted contributions and apply an exact threshold tie
   rule.
4. Add only an additive KB-06 draft-materialization seam; fragment code never
   derives a `UnitId` or calls a provider.
5. Verify table-driven decisions, replay determinism, malformed/bounded input,
   parent accessibility and index-growth bounds, custom unitizer versions, and
   import firewalls.

## Risks

- Adding `summary` and `item` to the shared unit-kind enum is a narrow public
  contract extension required by the parent specification.
- The tree admission type is supplied by KB-08 later; extraction accepts the
  admitted wrapper when present and performs the same canonical re-derivation
  for the plain-tree compatibility seam on this branch.

## Verification

- `python -m pytest tests/unit/knowledge/test_fragments.py tests/architecture/test_knowledge_boundaries.py -q`
- `ruff check src/study_agent/domain/fragments.py src/study_agent/knowledge/fragments.py src/study_agent/knowledge/unitizer.py tests/unit/knowledge/test_fragments.py`
- `mypy --strict src/study_agent/domain/fragments.py src/study_agent/knowledge/fragments.py src/study_agent/knowledge/unitizer.py`
