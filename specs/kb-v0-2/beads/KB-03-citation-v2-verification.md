# KB-03: Citation v2 and offline verification

Status: Done — implemented, security-reviewed, and verified 2026-07-27
Risk: High
Depends On: KB-01, KB-02
Parent coverage: §§4.1–5, 10.4, 12–14

## Outcome

Text and figure citations resolve mechanically from canonical bytes, expose
selection status and explicit succession, and cannot be forged by an index or
derived artifact.

## API seam

- Versioned `TextCitation`, `FigureCitation`, and `DerivedRef` contracts based
  on the KB-00 identity decision.
- One citation verifier port/owner for substrate spans and figure blobs.
- Exact result/failure vocabulary for missing, corrupt, out-of-unit,
  inactive-with-successor, mismatched-checksum, and unsupported-version cases.
- Explicit v0.1 citation decode/upgrade behavior.

## Acceptance criteria

- [x] Text verification checks substrate hash, span bounds, unit containment,
  and quoted checksum.
- [x] Figure verification checks blob hash; page and anchor remain hints/links,
  not image identity.
- [x] Derived text is always labeled and carries a canonical subject citation;
  it is never accepted as a citation.
- [x] Index text/snippets cannot override canonical bytes.
- [x] Inactive citations resolve with selection status and explicit successor
  information.
- [x] Unknown versions, cross-source/revision/unit mismatches, tampering, and
  malformed offsets fail closed.

## Verification

- `tests/unit/knowledge/test_citation_v2.py` (30 cases): contract suite,
  corruption and tampered-index adversarial cases, hostile encodings, and
  v0.1 compatibility fixtures.
- `pytest` 2146 passed / 12 skipped, `ruff check` clean, strict `mypy` clean.

## Review outcome

Independently security-reviewed. Findings fixed before closure:

- `selection_status` defaulted to `current`, so a caller who simply forgot the
  argument would silently report a superseded citation as current. The
  argument is now required, forcing an explicit decision at every call site.
- Invalid UTF-8 substrate bytes, and a lone surrogate in a v0.1 snippet, raised
  raw `ValueError`/`UnicodeError` instead of a typed `CitationFailure`,
  breaking the "always fails closed with a typed reason" contract for a caller
  that only catches `CitationFailure`. All Unicode failures are now typed.
- `locator` was unbounded; capped at 128 characters like other label fields.

## Caller obligation, recorded deliberately

`substrate_id` hashes content bytes only, so it carries no source or revision
binding. The only thing tying a citation to a source and revision is the
`RetrievableUnit` the caller supplies, and a fabricated but internally
consistent unit verifies here. That is by design: catching it is the KB-05
binding gate's job. The module docstring now states that `unit` must be looked
up in the canonical unit registry and never rebuilt from connector, request,
or model input, and the previous docstring claim that minting made rejection
impossible has been corrected.

Related: `DerivedRef.subject` is not verified at construction, so a consumer
that presents a subject citation as grounding must verify it first. When a v2
decoder is added it must reject on the `derived` marker before treating any
nested subject as a standalone citation.

Spans stay code-point exact per ADR-0014 and may split a grapheme cluster;
widening them would change what was cited, so this is accepted and documented
rather than silently corrected.

## Out of scope

- Retrieval ranking, automatic citation migration, or transport formatting.
