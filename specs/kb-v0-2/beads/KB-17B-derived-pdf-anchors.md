# KB-17B: Derived PDF figure anchors

Status: Proposed
Risk: Medium
Depends On: KB-15B, KB-17A
Parent: KB-17

## Outcome

PDF page geometry can propose bounded uncertain anchors using page maps and
document structure, with confidence derived from inspectable geometric signals.

## Acceptance criteria

- [ ] Bbox/page position maps through the exact substrate page map before
  selecting the nearest valid preceding heading.
- [ ] Caption proximity is only a deterministic tiebreak, never the primary
  association or a cross-document key.
- [ ] Confidence formula/version and all contributing signals are recorded.
- [ ] Out-of-page, ambiguous, missing-map, and malformed geometry produce typed
  provisional failure rather than an invented placement.
- [ ] Similarity/model output cannot establish an anchor.
- [ ] Same geometry/tree/policy yields the same provisional anchors.

## Verification

- Hand-labeled geometry fixtures, page-boundary/column/tie cases, and confidence
  bucket checks.
- Initial anchor precision/recall measurement by confidence bucket.

## Out of scope

- Human review, cross-document correspondence, OCR, or per-query matching.
