# KB-16: Incremental projection, indexing, and invalidation

Status: Proposed
Risk: High
Depends On: KB-02, KB-05, KB-08, KB-09B
Parent coverage: §§7.2, 11, 14; M6

## Outcome

Re-ingestion reuses unchanged unit-derived work, updates only affected
projections/index rows, and recovers atomically after crashes while historical
citations remain resolvable.

## API seam

- Unit diff plan based on the accepted KB-00 identity/cache decision.
- SQLite sync state is colocated transactionally with operational indexes.
- Fingerprint-keyed operational invalidation and audit state never becomes a
  canonical domain event; regenerated artifacts remain derived.
- Deterministic checkpoint/recovery contract for interrupted updates.

## Acceptance criteria

- [ ] Changing two sections only reprojects/reindexes those affected units.
- [ ] Removed current units leave active indexes but retain canonical historical
  substrate/citation resolution.
- [ ] Projector/model version changes invalidate exactly matching artifacts.
- [ ] Crash at every sync phase resumes without mixed old/new index state or
  duplicate canonical events.
- [ ] Full operational deletion and replay/regeneration satisfy the exact
  KB-00 replay contract.
- [ ] Sync state never becomes a second source of canonical truth.

## Verification

- Large-fixture two-section incrementality counters.
- Transaction fault injection at diff, projection, index, checkpoint, and
  finalize boundaries.
- Full delete/rebuild equivalence and historical-citation tests.

## Out of scope

- Automatic substrate GC or distributed multi-writer indexing.
