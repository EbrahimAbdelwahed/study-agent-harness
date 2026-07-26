# KB-09: Lexical projector and offline index surfaces

Status: Proposed parent — child beads own implementation
Risk: Medium
Depends On: KB-08
Parent coverage: §§7.1, 10.1, 14; M3

## Outcome

Offline search indexes regularized projection handles, rare terms/aliases, and
canonical text as separate retriever surfaces while preserving literal-query
safety.

## Child beads

- [KB-09A](KB-09A-lexical-projector.md): deterministic corpus-IDF terms and
  per-scope aliases.
- [KB-09B](KB-09B-sqlite-lexical-surfaces.md): discardable SQLite FTS surfaces,
  migration, and hostile-index verification.

## Out of scope

- Fusion, vector search, reranking, or alias-source selection policy.
