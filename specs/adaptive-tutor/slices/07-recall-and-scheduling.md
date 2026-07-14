# Slice 07: Recall and scheduling

## Outcome

Accepted flashcards accumulate immutable review evidence and deterministic due
work through a versioned scheduling decision.

## Contract

- Reviews record response, grade, latency, and confidence.
- Applied schedule decisions pin policy version and input fingerprint.
- The first policy is deterministic and dependency-free; an FSRS integration
  may follow behind the same seam.
- Anki remains export/integration, never canonical scheduling state.
