# Log: KB-09A lexical projector

Date: 2026-07-27 20:30
Area: knowledge-base

## Summary

Implemented the free lexical projector as a pure, deterministic derived layer.
The scope-local projector consumes admitted structural projections and exact
canonical text slices, computes smooth corpus-IDF terms, and applies bounded
literal aliases.  Unicode NFC/casefold normalization preserves accents, Greek
characters, and digit-bearing medical identifiers; no ASCII folding, query
parser, model, provider, or persistence dependency is present.

## Files Changed

- `src/study_agent/knowledge/lexical.py`: versioned policy, strict codecs,
  bounded corpus admission, deterministic token/IDF/alias calculation, and
  KB-08-compatible `IndexProjection` generation.
- `src/study_agent/knowledge/__init__.py`: public knowledge-package exports.
- `tests/unit/knowledge/test_lexical.py`: Unicode/medical golden cases, IDF
  ordering, aliases and collision safety, empty/small/duplicate/capped corpus,
  canonical-slice and structural admission, determinism, and codec tests.
- `specs/kb-v0-2/beads/KB-09A-lexical-projector.md`: marked complete.

## Verification

- `python -m pytest tests/unit/knowledge/test_lexical.py -q`: 8 passed.
- `python -m pytest tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py -q`: 369 passed.
- `ruff check src/study_agent/knowledge/lexical.py src/study_agent/knowledge/__init__.py tests/unit/knowledge/test_lexical.py`: passed.
- `python -m mypy --strict src/study_agent/knowledge/lexical.py src/study_agent/knowledge/__init__.py tests/unit/knowledge/test_lexical.py`: passed.

## Notes

- Duplicate unit IDs are accepted only when the full immutable corpus item is
  identical; conflicting input is rejected.
- Empty corpora and empty alias values are valid no-ops.  Alias collisions
  after normalization fail closed.  Aliases remain literal derived data and
  are never compiled as FTS/query syntax.
- Each effective algorithm, normalization, stop, IDF, alias, and cap choice is
  versioned in `LexicalPolicy` and contributes to the KB-08 input fingerprint.
