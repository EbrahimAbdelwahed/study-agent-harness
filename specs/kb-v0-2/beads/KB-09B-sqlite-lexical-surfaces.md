# KB-09B: SQLite lexical retrieval surfaces

Status: Implemented — pending orchestrator review
Risk: High
Depends On: KB-03, KB-09A
Parent: KB-09

## Outcome

SQLite FTS indexes `lex_projection`, `lex_terms`, and `lex_canonical` as
discardable surfaces behind portable contracts, with a defined v0.1 migration.

## Acceptance criteria

- [x] Existing literal query compilation remains the one query-safety owner or
  is replaced exactly as KB-00 directs.
- [x] Each surface returns portable IDs/ranks/scores, never SQLite row objects.
- [x] Index text is never trusted as canonical evidence; results resolve through
  KB-03.
- [x] Schema migration/rebuild is atomic, idempotent, versioned, and recoverable.
- [x] Projection deletion/index rebuild yields equivalent candidates.
- [x] Prompt injection, FTS operators, punctuation, malformed rows, stale
  projection refs, and tampered text fail safely.

## Verification

- SQLite contract/integration tests and v0.1 migration fixture.
- Injection, transaction fault, corruption, and rebuild adversarial tests.
- Fixed medical query eval over all three surfaces.

## Implementation notes

- `LexicalProjectionBinding` is the canonical catalog boundary.  A binding
  carries an explicit `ScopeId`, `IndexProjection`, `RetrievableUnit`, exact
  substrate bytes, revision-selection status, and scope-membership bit.
- `SQLiteLexicalSurfaces` owns only discardable rows.  It re-derives projection
  identity, checks the complete catalog before any write, validates the unit's
  `TextSpan` through the KB-03 citation verifier, and returns no indexed text.
- `literal_query.py` is now the sole compiler owner.  The v0.1 adapter delegates
  to `unicode61-v1`; the v0.2 adapter uses `medical-trigram-v1` and KB-09A
  tokenization.

## Out of scope

- Fusion, vector search, or public evidence packets.
