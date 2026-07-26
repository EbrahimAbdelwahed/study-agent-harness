# KB-18: Figure inheritance and direct lexical retrieval

Status: Proposed
Risk: Medium
Depends On: KB-12, KB-13, KB-17C
Parent coverage: §§9.2–9.3, 10, 12; M7

## Outcome

Text evidence inherits structurally anchored figures, while secondary direct
figure search remains host-unit constrained and uses the same registry,
fusion, evidence, and citation shapes.

## API seam

- `FigureAttachment` carries verified figure citation, anchor, confidence,
  role/kind, ordering, and explicitly derived metadata.
- Inheritance attaches figures from matched unit and ancestors after ranking.
- `lex_figure` and `figures()` query caption/available labels, then reattach and
  filter against relevant host units.

## Acceptance criteria

- [ ] Default text retrieval decides relevance once and attaches figures in
  deterministic anchor confidence/document order.
- [ ] Direct figure candidates without a relevant host unit are excluded.
- [ ] Figure and host lexical scores remain separately inspectable before their
  documented blend.
- [ ] Rejected anchors never attach; provisional uncertainty stays visible.
- [ ] Figure attachments cannot change the text citation or fused text rank.
- [ ] The path works without OCR, vision, vectors, or models.

## Verification

- Fixtures for own-unit/ancestor inheritance, duplicates, rejected anchors,
  irrelevant host filtering, and deterministic ordering.
- Figure retrieval eval before any derived labels/cards.

## Out of scope

- OCR, figure cards/surrogates, direct image similarity, or review UI.
