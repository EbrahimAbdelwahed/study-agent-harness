# Task Bead: GAP-04B first source-format workaround adapter

Status: Ready — PDF-to-Markdown adapter approved 2026-07-26
Priority: P2
Type: tracer-bullet
Depends On: GAP-03, GAP-04A

## Outcome

One explicitly selected local converter demonstrates a sandboxed, provenance-
preserving temporary path without pretending it is native format support.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Optional concrete workaround after the reporting MVP proves useful.

## Grilling Evidence

- Session/artifact: user decision 2026-07-26 and ADR-0013.
- Decision state: local PDF-to-Markdown only; `pypdf==6.14.2` is an optional
  adapter dependency and the core remains dependency-free.
- ADR/glossary changes: ADR-0013 records dependency, effects, provenance,
  isolation, and explicit no-OCR limitations.

## Worker Profile

create `local-pdf-workaround` implementation profile

Rationale: PDF/OCR/audio have materially different dependencies and safety.

## Acceptance Criteria

- [ ] The optional pinned dependency, process isolation, file/page/output
  limits, race/symlink behavior, quality warning, and provenance are tested.
- [ ] Failure returns a truthful workaround receipt and preserves the gap report.
- [ ] The derived Markdown is byte-deterministic and can be ingested explicitly
  through the existing text path without treating the PDF as native support.

## Verification

- Adapter-specific hostile-file, quality, provenance, and offline tests.

## Out Of Scope

- OCR, native/general PDF support, automatic ingestion, images, layout/table
  reconstruction, models, network conversion, and hosted transport.
