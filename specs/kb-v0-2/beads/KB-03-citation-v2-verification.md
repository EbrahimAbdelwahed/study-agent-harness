# KB-03: Citation v2 and offline verification

Status: Proposed
Risk: High
Depends On: KB-01, KB-02
Parent coverage: §§4.1–5, 10.4, 12–14

## Outcome

Text and figure citations resolve mechanically from canonical bytes, expose
revision status, and cannot be forged by an index or derived artifact.

## API seam

- Versioned `TextCitation`, `FigureCitation`, and `DerivedRef` contracts based
  on the KB-00 identity decision.
- One citation verifier port/owner for substrate spans and figure blobs.
- Exact result/failure vocabulary for missing, corrupt, out-of-unit,
  superseded, mismatched-checksum, and unsupported-version cases.
- Explicit v0.1 citation decode/upgrade behavior.

## Acceptance criteria

- [ ] Text verification checks substrate hash, span bounds, unit containment,
  and quoted checksum.
- [ ] Figure verification checks blob hash; page and anchor remain hints/links,
  not image identity.
- [ ] Derived text is always labeled and carries a canonical subject citation;
  it is never accepted as a citation.
- [ ] Index text/snippets cannot override canonical bytes.
- [ ] Superseded citations resolve with status and successor information.
- [ ] Unknown versions, cross-source/revision/unit mismatches, tampering, and
  malformed offsets fail closed.

## Verification

- Reusable citation contract suite.
- Corruption and tampered-index adversarial tests.
- Compatibility fixtures for v0.1 citations and exports.

## Out of scope

- Retrieval ranking, automatic citation migration, or transport formatting.
