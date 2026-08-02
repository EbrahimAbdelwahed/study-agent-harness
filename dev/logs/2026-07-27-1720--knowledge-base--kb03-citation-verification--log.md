# Log: KB-03 citation v2 and offline verification

Date: 2026-07-27 17:20
Area: knowledge-base

## Summary

Implemented KB-03 and closed it after an independent security review. Text and
figure citations now resolve mechanically from canonical bytes, carry
selection status and explicit succession, and cannot be forged by an index or
a derived artifact.

## Files Changed

- `src/study_agent/domain/citation_v2.py`: `TextCitationV2`,
  `FigureCitationV1`, `DerivedRef`, `CitationFailureKind`, `CitationFailure`.
- `src/study_agent/knowledge/citation.py`: the verifier, minting, and the v0.1
  upgrade seam.
- `src/study_agent/domain/__init__.py`: additive exports.
- `tests/unit/knowledge/test_citation_v2.py`: 30 cases.
- `specs/kb-v0-2/beads/KB-03-citation-v2-verification.md`,
  `specs/kb-v0-2/README.md`.

## Security review findings fixed

- **Supersession could be silently hidden.** `selection_status` defaulted to
  `current`, so any call site that forgot the argument reported a superseded
  citation as current. Now required.
- **Untyped failures at the trust boundary.** Invalid UTF-8 substrate bytes
  and a lone surrogate in a v0.1 snippet raised raw `ValueError` /
  `UnicodeError`, so a caller catching only `CitationFailure` would crash
  instead of failing closed. All three paths were reproduced and are now
  typed.
- **Unbounded `locator`.** Capped at 128 characters.

## Recorded rather than fixed

- A caller-supplied `RetrievableUnit` is the only thing binding a citation to a
  source and revision, because `substrate_id` hashes content bytes only. A
  fabricated but internally consistent unit verifies here. This is the KB-05
  binding gate's responsibility, not this module's; the obligation is now
  stated in the module docstring and the bead, and the previous docstring
  claim that minting made later rejection impossible was wrong and is
  corrected.
- Spans stay code-point exact per ADR-0014 and may split a grapheme cluster.
  Widening a span would change what was cited, so this is documented instead.

## Verification

- `pytest`: 2146 passed, 12 skipped (2116 before this change).
- `ruff check .` clean, strict `mypy` clean (495 files), `git diff --check`
  clean.
