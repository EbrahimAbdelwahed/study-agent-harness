# Plan: KB-06 structural unitizer

Date: 2026-07-27 16:00
Area: knowledge base

## Goal

Add a deterministic, corpus-agnostic unitizer that turns the KB-04 document
tree and canonical revision binding into document/section/passage units while
preserving atomic structural regions and the v0.1 1,200-character fallback.
Expose a versioned policy, final unit-id ownership, and conservative citation
remapping for policy/version changes.

## Scope

- In scope: `src/study_agent/knowledge/unitizer.py`, focused unitizer tests,
  KB-06 status, and a factual completion log.
- Out of scope: connectors, indexing/projections beyond consuming the existing
  `RevisionBinding`/`reduce_units` seam, model calls, new dependencies, and
  unrelated domain refactors.

## Approach

1. Define immutable `UnitizerPolicy`, `UnitDraft`, and remap report contracts
   with a versioned cap and 1,200-character structure-poor fallback.
2. Unitize tree nodes without crossing node boundaries; emit document and
   section ladder rows plus paragraph-boundary passages, keeping table,
   emphasis, and code regions atomic.
3. Build final `RetrievableUnit` identities locally from canonical spans and
   supplied revision/source metadata; provide a conservative exact-span remap.
4. Add boundary, Unicode, determinism, atomic-region, fallback, and remap
   tests; update the bead and record verification.

## Risks

- Existing tree nodes are structural regions nested under body/section nodes;
  avoid duplicate or overlapping ladder rows by treating only body/heading
  nodes as section candidates and typed regions as passage atoms.
- The existing strict unit contract requires non-empty spans and a valid
  `UnitMeta`; the unitizer must fail closed on empty input rather than invent
  canonical text.

## Verification

- `pytest -q tests/unit/knowledge/test_unitizer.py`
- `ruff check src/study_agent/knowledge/unitizer.py tests/unit/knowledge/test_unitizer.py`
- `mypy src/study_agent/knowledge/unitizer.py`
- `pytest -q tests/unit/knowledge`
