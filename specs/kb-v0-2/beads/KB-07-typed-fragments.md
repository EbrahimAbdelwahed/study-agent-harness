# KB-07: Typed fragments and promotion gate

Status: Proposed
Risk: Medium
Depends On: KB-06
Parent coverage: §§5.1–5.2, 8.3–8.4

## Outcome

High-signal emphasis, summary, definition, table, and item regions become
fine-grained units through a deterministic per-scope policy instead of
exhaustive fragmentation.

## API seam

- Generic fragment drafts originate from tree regions.
- One model-free `FragmentPromotionPolicy` consumes length, structural weight,
  corpus rarity, and reference signals and returns an inspectable decision.
- Scope configuration validates bounded weights/thresholds and records version.

## Acceptance criteria

- [ ] Promotion decisions are deterministic and include contributing signals.
- [ ] High-IDF, minimum-length, structurally weighted, and referenced signals
  behave independently and in combination.
- [ ] Low-information fragments remain reachable through their parent passage.
- [ ] Atomic fragments preserve exact canonical spans and inherited flags.
- [ ] Tuning scope policy does not mutate canonical substrate or tree state.
- [ ] No model, embedding, tutor preference, or flashcard heuristic enters the
  gate.

## Verification

- Table-driven threshold and tie-boundary tests.
- Corpus fixture demonstrating index-growth bounds and retained parent access.
- Semantic review of defaults before they become public configuration.

## Out of scope

- Pedagogical preference, semantic classification, or retrieval fusion.
