# Plan: KB-08 projection core and structural projector

Date: 2026-07-27 18:00
Area: knowledge-base

## Goal

Add strict provider-neutral projection values and a deterministic structural
projector over admitted canonical units and ancestor headings. Derived
projections are independently versioned, deletable, and rebuildable while
canonical unit and citation state remains untouched.

## Scope

- In scope: `domain/projections.py`, `knowledge/projections.py`, tree admission
  required by A3, focused projection and architecture tests, KB-08 bead status,
  and a KB-08 development log.
- Out of scope: lexical/model/vector/OCR/retrieval adapters, corpus-specific
  dialect behavior, schema/dependency changes, and canonical evidence text.

## Approach

1. Define bounded frozen projection values with strict codecs and ADR-0014
   identity/fingerprint derivation.
2. Add substrate-backed tree admission that re-derives the deterministic tree
   and rejects persisted span/identity/structure tampering before projection.
3. Implement a model-free structural projector port and safe heading fallback;
   keep outputs in separate discardable projection state with delete/rebuild
   helpers.
4. Add clean-room, bounds/forgery, provenance, deletion/rebuild, and architecture
   tests; export only the approved public contracts.

## Risks

- Hidden consumers may rely on exact field names and canonical tuple encoding;
  codecs fail closed on unknown or missing fields.
- Tree spans are not identity-bearing, so admission compares the rebuilt tree
  against the substrate/profile and rejects any mismatch.

## Verification

- `PYTHONPATH=src:. pytest -q tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py`
- `ruff check` on changed source/tests.
- `mypy` on changed modules when available.
