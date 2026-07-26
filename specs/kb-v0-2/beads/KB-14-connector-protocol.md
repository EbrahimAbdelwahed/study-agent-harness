# KB-14: Source connector protocol and conformance boundary

Status: Proposed
Risk: High
Depends On: KB-00, KB-01, KB-04, KB-05
Parent coverage: §§6–6.1, 8; M4

## Outcome

New source types plug into one connector boundary that translates media/dialect
into generic substrate/tree/unit drafts while safety and final unit identity
remain owned by the KB.

## API seam

- `ConnectorManifest`, capability declaration, `SourceConnector` protocol,
  generic dialect profile, and `ConformanceReport`.
- Pin the division between connector-produced drafts and unitizer-owned final
  units according to KB-00.
- Conformance severities describe structural quality; canonical integrity and
  safety validation remain separate blocking gates.

## Acceptance criteria

- [ ] A connector declares accepted media, class/role/trust defaults,
  capabilities, version, and answering hints.
- [ ] Missing optional capability records a skip/degradation reason without
  impersonating successful ingestion.
- [ ] Structural conformance errors may trigger the universal window fallback;
  unsafe bytes, corrupt provenance, invalid spans, and forged IDs reject.
- [ ] Dialect constructs do not enter domain enums or retrieval callers.
- [ ] Connector output is bounded, deterministic for the same inputs/version,
  and validated before canonical append.
- [ ] No connector creates its own index, result type, scorer, or unit identity.

## Verification

- Reusable connector conformance test kit with a minimal fake connector.
- Adversarial capability spoofing, malformed draft, oversized output, unsafe
  media, and integrity/conformance separation tests.
- Architecture review of all ownership boundaries.

## Out of scope

- Concrete PDF converter/transcriber implementation or baseline profiles.
