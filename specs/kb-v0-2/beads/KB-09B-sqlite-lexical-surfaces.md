# KB-09B: SQLite lexical retrieval surfaces

Status: Proposed
Risk: High
Depends On: KB-03, KB-09A
Parent: KB-09

## Outcome

SQLite FTS indexes `lex_projection`, `lex_terms`, and `lex_canonical` as
discardable surfaces behind portable contracts, with a defined v0.1 migration.

## Acceptance criteria

- [ ] Existing literal query compilation remains the one query-safety owner or
  is replaced exactly as KB-00 directs.
- [ ] Each surface returns portable IDs/ranks/scores, never SQLite row objects.
- [ ] Index text is never trusted as canonical evidence; results resolve through
  KB-03.
- [ ] Schema migration/rebuild is atomic, idempotent, versioned, and recoverable.
- [ ] Projection deletion/index rebuild yields equivalent candidates.
- [ ] Prompt injection, FTS operators, punctuation, malformed rows, stale
  projection refs, and tampered text fail safely.

## Verification

- SQLite contract/integration tests and v0.1 migration fixture.
- Injection, transaction fault, corruption, and rebuild adversarial tests.
- Fixed medical query eval over all three surfaces.

## Out of scope

- Fusion, vector search, or public evidence packets.
