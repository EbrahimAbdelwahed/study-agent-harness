# Task Bead: TUT-04C grounded flashcard proposal capabilities

Status: Blocked on TUT-04A and TUT-03
Priority: P0
Type: expand
Depends On: TUT-04A, TUT-03

## Outcome

`propose_flashcards@1` generates a bounded, source-grounded proposal batch using
one trusted pedagogical profile selected by the host.

## Child Beads

- [TUT-04C0 — shared flashcard batch and trusted dispatch](TUT-04C0-flashcard-batch-and-dispatch.md)
- [TUT-04C1 — hybrid macro-detail implementation](TUT-04C1-hybrid-flashcard-profile.md)
- [TUT-04C2 — morphology-first anatomy implementation](TUT-04C2-morphology-flashcard-profile.md)
- [TUT-04C3 — profile gateway and adversarial evals](TUT-04C3-flashcard-profile-evals.md)

## Acceptance Criteria

- [ ] Hybrid profile indexes the bounded source scope, treats budgets as
  ceilings, emits framework before earned details, resolves parent linkage, and
  rejects overlap, duplicates, unsupported claims, and more than 24 cards.
- [ ] Morphology profile clusters anatomical objects/regions, validates bounded
  reconstruction plus earned discriminations, keeps contextual deletion
  selective, and rejects unverified media or spatial claims.
- [ ] Shared content is exporter-neutral: no deck, Anki tags, raw HTML, provider
  selector, credential, or live Anki operation.
- [ ] Prompt layers treat source, examples, continuation, and candidate keys as
  untrusted data; validators derive canonical-safe batch output and provenance.
- [ ] Capability has empty state-write policy and cannot accept proposals.

## Verification

- Profile-specific prompt/validator fixtures, direct gateway evals, injection,
  source gaps, budget/parent overlap, tool parity, and full gates.
