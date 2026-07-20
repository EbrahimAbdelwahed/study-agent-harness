# Slice 07: Recall and scheduling

## Outcome

Accepted flashcards accumulate immutable review evidence and deterministic due
work through a versioned scheduling decision.

## Contract

- Reviews record response, grade, latency, and confidence.
- Applied schedule decisions pin policy version and input fingerprint.
- The core seam and offline fake policy are dependency-free. The reference
  production policy uses exact-pinned `fsrs==6.3.1` through the optional
  `[recall]` adapter; package state never enters canonical events or replay.
- Anki remains export/integration, never canonical scheduling state.
