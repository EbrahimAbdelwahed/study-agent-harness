# Log: KB-05 uniform retrievable units, plus review hardening

Date: 2026-07-27 14:50
Area: knowledge-base

## Summary

Implemented KB-05: one strict provider-neutral row shape for every indexable
text, figure, table, fragment, and exam item, with one replayable projected
owner. Then hardened KB-02, KB-04, and KB-05 against the findings of an
independent code review and an independent security review.

## Files Changed

- `src/study_agent/domain/units.py`: new `UnitKind`, `ReviewStatus`,
  `LinkKind`, `TextSpan`, `FigureBlob`, `CanonicalRef`, `UnitMeta`,
  `UnitLink`, `UnitSignal`, `RetrievableUnit`, `decode_canonical_ref`.
- `src/study_agent/domain/identifiers.py`: `UnitId` and `unit_id_for`.
- `src/study_agent/knowledge/units.py`: `UNITIZER_VERSION`,
  `RevisionBinding`, `admit`, `reduce_units`, `decode_unit`,
  `unit_from_legacy_chunk`.
- `src/study_agent/knowledge/tree.py`: performance and correctness fixes.
- `src/study_agent/ingestion/succession.py`: performance fix, fail-closed fix.
- `tests/unit/knowledge/test_retrievable_units.py` (54 cases),
  `tests/architecture/test_knowledge_boundaries.py`.

## Review findings fixed

Code review (0 critical, 1 high, 1 medium, 2 low) and security review
(2 high, 3 medium, 2 low). KB-02 and KB-04 passed the code review clean; every
finding below was fixed and given a regression test.

1. **Link integrity (high).** A link to a non-existent unit was persisted, and
   two units with reciprocal `PARENT` links were undetected. `reduce_units`
   now validates the batch transactionally: every non-provisional target must
   be known, parent chains must be acyclic, and nothing is written if any unit
   fails.
2. **Forged evidence (high).** `admit()` only proved hash self-consistency.
   Since ADR-0014 excludes `source_id` and the substrate from `unit_id`, a
   unit could name a real span under a high-trust source it did not belong to,
   or name a revision that was never ingested. `reduce_units` now requires
   `RevisionBinding` values from the caller and checks source ownership,
   substrate binding, and span bounds against real state.
3. **Text smuggling (medium).** `provisional_target`, `flags`, `role`,
   `source_class`, `language`, and path segments were unbounded, giving a
   second channel for canonical text around the "units never carry text"
   invariant. All are capped at 128 characters.
4. **Quadratic succession scan (medium/high, already live).** `_successor_in`
   scanned every edge, and `_reaches` called it per hop, so one append was
   O(n²) in accumulated edges. Measured by the reviewer at 800 edges → 1.17 s.
   The predecessor lookup is now built once per call; the persisted shape
   stays an append-ordered array so no separator can be ambiguous.
5. **Quadratic tree scan (medium/high).** `_regions` and `_markers_in`
   re-scanned every line of the document per node, and `_nest` re-scanned the
   remaining headings per heading. Measured 16k headings → 15.4 s. Replaced
   with a bisect line window and a single-pass stack. Now 16k headings →
   0.42 s, and scaling is linear (2k → 0.05 s, 4k → 0.10 s).
6. **Segment dedup could itself collide (low).** Headings `Intro`, `Intro-2`,
   `Intro` made the whole document fail with an opaque `ValueError`. The
   suffix counter now retries until the label is genuinely free.
7. **`_production_for` failed open (low).** Malformed projection data silently
   returned "legacy substrate" instead of raising; now fails closed like the
   rest of the module.
8. Dead `granularity_for` export removed; redundant filter simplified.

## Verification

- `pytest`: 2116 passed, 12 skipped (2043 before this change).
- `ruff check .` clean, strict `mypy` clean (492 files), `git diff --check`
  clean.
- Re-measured both performance fixes directly after the change.

## Deferred, recorded in the README human-review map

- `node_id` still does not commit to `span`. Safe inside
  `build_document_tree`, and `node_id` is documented as a structural handle
  only, but before KB-08 trusts a persisted tree span evidentially, either
  bind `span` into `node_id` or add a tree admission function. Binding `span`
  now would churn every `node_id` whenever preceding text is inserted, which
  is exactly the reuse ADR-0014 wants preserved, so this needs a decision
  rather than a reflex.
