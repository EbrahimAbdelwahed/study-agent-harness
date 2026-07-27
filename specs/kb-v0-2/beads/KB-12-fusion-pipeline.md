# KB-12: Deterministic fusion, collapse, diversity, and expansion

Status: Implementation complete — awaiting semantic review
Risk: Medium
Depends On: KB-05, KB-07, KB-11
Parent coverage: §§10.2–10.4; M5

## Outcome

Registered candidate lists deterministically become diverse evidence groups
through weighted RRF, granularity collapse, dedupe, priors, and post-rank
expansion.

## API seam

- Pure fusion policy over registry candidates; RRF constant defaults to 60.
- One ladder-collapse owner uses unit ancestry to choose a representative.
- Source/section diversity caps and structural/review/uncertainty priors are
  explicit per-scope policy inputs.
- Expansion runs only after final ranking and keeps narrow evidence separate.

## Acceptance criteria

- [x] Consensus and weights follow the documented RRF formula.
- [x] Multiple granularities of the same content occupy one result group.
- [x] Dedupe and diversity caps have deterministic tie-breaking.
- [x] Source class and review priors are reported; uncertainty is demoted and
  always preserved as a flag.
- [x] No recency prior exists.
- [x] Parent/sibling/window expansion cannot alter the narrow cited span.
- [x] Empty candidates produce an explicit insufficient result.

## Verification

- Golden ranking vectors for one/many retrievers, ties, missing retrievers, and
  weight changes.
- Adversarial ladder duplication and source-monopoly fixtures.
- Property tests for permutation stability and bounded output.

## Out of scope

- Reranking, figure attachment, or canonical citation resolution.
