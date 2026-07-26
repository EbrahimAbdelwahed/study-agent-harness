# KB-17A: Figure units and structural anchors

Status: Proposed
Risk: High
Depends On: KB-03, KB-05, KB-14, KB-16
Parent: KB-17

## Outcome

Exact image bytes become uniform content-addressed figure units with
deterministic exact/generated anchors and verifiable figure citations.

## Acceptance criteria

- [ ] Figure identity is exact image SHA-256; duplicate image bytes share one
  figure identity and keep distinct placements.
- [ ] Figure blobs retain extraction/origin provenance and bounded media
  metadata without trusting parser text.
- [ ] Authored embeds and canonical generated markers produce confidence-1.0
  anchors with deterministic IDs/order.
- [ ] Anchor offsets lie inside known host units and cannot cross revisions.
- [ ] Figure citations verify exact bytes through KB-03.
- [ ] Malformed/oversized/unsupported images fail before event append through a
  separately reviewed extraction boundary.

## Verification

- Event/codec/replay, duplicate-image, offset-boundary, and blob-corruption
  tests.
- Hostile image/extractor security review.

## Out of scope

- PDF geometry inference, review decisions, OCR, captions, or retrieval.
