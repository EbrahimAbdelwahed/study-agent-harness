# KB-15A: Markdown and plain-notes connectors

Status: Proposed
Risk: Medium
Depends On: KB-06, KB-07, KB-14
Parent: KB-15

## Outcome

Markdown documents and structure-poor personal notes exercise the connector
contract with no optional dependency or generated normalization.

## Acceptance criteria

- [ ] Markdown headings, paragraphs, tables, code, and generic regions map to
  KB-owned tree/unit drafts.
- [ ] Plain notes ingest as-is with weaker self-containment findings and the
  universal window fallback.
- [ ] Structural warnings never alter canonical bytes.
- [ ] Profiles declare media, class/role/trust defaults, capability `none`, and
  version.
- [ ] No connector-specific unit/result/index type is introduced.

## Verification

- Golden fixtures plus connector conformance suite.
- Regression against v0.1 Markdown/plain-text ingestion and fallback windows.

## Out of scope

- Study-material dialect, PDF page maps, exam items, or model repair.
