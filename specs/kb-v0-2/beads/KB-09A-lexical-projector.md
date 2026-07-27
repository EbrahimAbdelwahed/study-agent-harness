# KB-09A: Lexical projector

Status: Complete
Risk: Medium
Depends On: KB-08
Parent: KB-09

## Outcome

The free lexical projector deterministically enriches structural projections
with corpus-IDF key terms and versioned per-scope aliases.

## Acceptance criteria

- [x] IDF computation, tokenization, normalization, stop policy, tie-breaking,
  and term caps are versioned and deterministic.
- [x] Rare technical identifiers and Unicode medical terms remain searchable.
- [x] Alias dictionaries are bounded, canonical, per-scope inputs and cannot
  inject query syntax.
- [x] Empty/small corpora and alias collisions have explicit behavior.
- [x] Same unit/corpus/policy produces byte-identical projection.
- [x] No model, embedding, external terminology source, or SQLite import enters
  the projector.

## Verification

- Golden corpus tests for IDF/order/aliases and medical Unicode terms.
- Boundary/property tests for empty corpus, ties, duplicates, and caps.

## Out of scope

- Choosing how alias dictionaries are authored or persisting/searching them.
