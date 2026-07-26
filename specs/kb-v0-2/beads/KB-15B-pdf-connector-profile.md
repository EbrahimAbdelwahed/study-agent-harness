# KB-15B: PDF connector profile over external substrate

Status: Proposed
Risk: Medium
Depends On: KB-01, KB-06, KB-14
Parent: KB-15

## Outcome

The PDF connector consumes an already converted, versioned Markdown substrate
and page map while preserving original PDF lineage and refusing to own
conversion internals.

## Acceptance criteria

- [ ] Input binds original PDF blob, exact substrate, converter receipt/version,
  normalization version, and page map.
- [ ] Page hints derive mechanically and never enter citation identity.
- [ ] Missing/invalid converter provenance or page-map bounds reject as
  integrity failures, not conformance warnings.
- [ ] Re-conversion creates a new revision and preserves old citation
  resolvability.
- [ ] Base package retains no PDF parser/converter dependency through this
  connector.

## Verification

- Scripted external-converter receipt fixtures.
- Page-map boundaries, reconversion, missing provenance, and mismatch tests.
- Architecture test excluding converter implementation imports.

## Out of scope

- PDF parsing, OCR, image extraction, or dependency selection.
