# KB-19: Exam item units and link-graph retriever

Status: Proposed
Risk: Medium
Depends On: KB-05, KB-12, KB-14, KB-15A
Parent coverage: §§9.6, 10.1, 12

## Outcome

Exam questions retain typed assessment structure as uniform units, and derived
item↔unit/prerequisite links become a model-free registered retriever rather
than being flattened into prose.

## API seam

- Exam-item payload covers stem, options, answer, rationale, item kind, and
  referenced figures with strict canonical/derived separation.
- The `exam_bank` connector maps source records to that single item contract.
- Derived `UnitLinks` connect items to teaching units with provenance and
  invalidation.
- `link_graph` retriever returns neighbors of already matching units through
  the KB-11 candidate contract.

## Acceptance criteria

- [ ] MCQ, open, true/false, matching, and image-based items validate through
  one generic item contract.
- [ ] Item citations target exact canonical item spans/figure blobs.
- [ ] Wrong derived teaching links can degrade recall but cannot modify
  canonical item/evidence state.
- [ ] Link traversal is bounded, cycle-safe, deterministic, and provenance-rich.
- [ ] `items()` filters by typed fields without tutor/session policy.
- [ ] No item is prose-windowed or indexed through a special result type.

## Verification

- Contract fixtures for all item kinds and malformed answer/option shapes.
- Link invalidation, cycle, cross-scope, and bounded-neighbor tests.
- Retrieval eval for “questions testing this section.”

## Out of scope

- Generating exam simulations, grading, learner attempts, or practice-set
  selection.
