# Plan: KB-09A lexical projector

Date: 2026-07-27 20:00
Area: knowledge-base

## Goal

Add a pure, deterministic lexical projector that enriches admitted structural
projections with bounded corpus-IDF terms and per-scope aliases while keeping
canonical units and projection identity authoritative elsewhere.

## Scope

- In scope: versioned lexical policy/codec, Unicode-aware tokenization and
  normalization, deterministic IDF and tie ordering, bounded alias policy,
  lexical projection composition, focused tests and import-boundary coverage.
- Out of scope: SQLite, persistence, query parsing/execution, retriever
  registry/fusion, external terminology, models, embeddings, and product code.

## Approach

1. Define a frozen policy with explicit algorithm/version and finite bounds.
2. Validate an immutable corpus of canonical unit text plus KB-08 structural
   projections and derive one IndexProjection per unit.
3. Use Unicode normalization without ASCII folding; preserve digit-bearing and
   medically meaningful identifiers, and treat aliases as literal data.
4. Hash effective corpus/policy inputs through the KB-08 projection fingerprint
   and retain the existing IndexProjection schema/provenance.
5. Add golden and adversarial tests for determinism, IDF, Unicode, aliases,
   empty/small/tied/duplicate/capped corpora and provider import firewall.

## Risks

- Token policy affects retrieval quality; freeze all choices in the versioned
  policy and keep changes invalidating via projector version.
- Unit text is canonical input but remains derived output only; no text is
  copied into the projection schema.
- Corpus-wide calculations must reject malformed, non-finite, or unbounded
  input before producing any rows.

## Verification

- `.venv/bin/python -m pytest tests/unit/knowledge/test_lexical.py tests/architecture/test_knowledge_boundaries.py`
- `.venv/bin/ruff check src/study_agent/domain src/study_agent/knowledge tests/unit/knowledge/test_lexical.py`
- `.venv/bin/python -m mypy --strict <changed source files>`
