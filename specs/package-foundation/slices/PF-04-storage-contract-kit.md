# PF-04 — Storage contract kit

Status: Complete

## Outcome

Hosts can supply narrow storage, clock, ID, and repository ports while the
reference SQLite event/run stores and filesystem blob store pass one reusable
offline contract kit. The kit proves optimistic concurrency, immutable blobs,
replay equality, and adapter error translation without making any adapter the
domain authority.

## Non-goals

- No distributed queue, JobStore, lease, retry worker, or hosted persistence.
- No path discovery, global repository singleton, implicit directory creation,
  or Cardine-owned storage layout.
- No migration of existing debug data and no schema change outside the named
  storage ports.

## Exact contracts

- Public storage ports are typed protocols: `EventStore`, `BlobStore`,
  `RunStore`, `Repository`, `Clock`, and `IdFactory`. A host supplies them in
  dependency injection; the harness never locates them globally.
- Event-store operations preserve the PF-03 envelope and per-stream sequence:
  append requires expected sequence and idempotency key; read accepts a stream
  and high-water position; a sequence mismatch is `StaleFailure`; an equal key
  with different bytes is `ConflictFailure`.
- Blob storage is content-addressed by lowercase SHA-256 and immutable. `put`
  returns an existing reference for equal bytes, rejects a checksum/length
  mismatch, and never overwrites bytes. `get` missing data maps to
  `NotFoundFailure` and corruption maps to `InternalFailure` or a typed
  integrity validation failure.
- `RunStore` is operational only. Its records may be discarded and rebuilt;
  they cannot become canonical learner state. Compare-and-set operations are
  atomic and return a typed conflict rather than silently overwriting.
- `Clock.now()` returns an aware UTC instant. `IdFactory` creates typed IDs
  without random global state hidden from tests. Test clocks and deterministic
  ID factories are supported ports.
- `Repository` groups the event, blob, source, and operational ports but does
  not add a second transaction authority. Cardine owns physical paths and
  composes the repository.
- The contract kit is parametrized over memory, SQLite, and filesystem
  adapters. It runs the same scenarios against each adapter and compares
  canonical serialized results byte-for-byte.
- Public service methods may be async where an operation can suspend. A
  synchronous reference adapter may sit behind the runtime adapter, but it
  cannot create a parallel state machine or alter event semantics.

## Probable files

- `src/study_agent/api/storage.py` — public port exports.
- `src/study_agent/ports/storage.py` — protocol and result updates.
- `src/study_agent/ports/clock.py` and `src/study_agent/ports/id_factory.py` —
  deterministic host ports.
- `src/study_agent/adapters/sqlite/event_store.py`,
  `src/study_agent/adapters/sqlite/run_store.py`, and
  `src/study_agent/adapters/filesystem/blob_store.py` — reference adapters.
- `tests/contract/storage/test_event_store_contract.py`,
  `tests/contract/storage/test_blob_store_contract.py`,
  `tests/contract/storage/test_replay_contract.py`, and
  `tests/contract/storage/test_capability_storage_contract.py`.
- `tests/integration/test_filesystem_blob_store.py`,
  `tests/contract/event_store/test_sqlite_event_store.py`, and
  `tests/contract/run_store/test_sqlite_run_store.py`.

## Dependencies

PF-01 supplies the public storage subfacade, PF-02 supplies errors and
idempotency, and PF-03 supplies the event envelope and replay rules. PF-05,
PF-06, PF-07, and PF-08 consume this contract kit.

## Removal conditions

Remove any adapter-specific public exception, serializer, or path helper from
the facade before acceptance. A compatibility wrapper may remain private only
while its named consumer migrates and must not define alternate canonical
bytes.

## Review surface

Review protocol narrowness, async/sync boundary, CAS behavior, SHA-256 blob
identity, and the shared contract-test parametrization. Inspect a failed
SQLite transaction and a missing/corrupt blob to confirm safe typed errors and
no partial canonical append.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/storage tests/contract/event_store tests/contract/blob_store tests/contract/run_store
uv run --python 3.13 --extra dev pytest -q tests/integration/test_filesystem_blob_store.py tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py
uv run --python 3.13 --extra dev ruff check src/study_agent/ports src/study_agent/adapters/sqlite src/study_agent/adapters/filesystem tests/contract/storage
git diff --check
```

The kit must cover empty streams, stale sequence, equal-key retry, changed
input conflict, transaction rollback before append, equal-byte blob dedupe,
checksum corruption, CAS races, UTC clock behavior, and projection replay
equality across memory and SQLite.

## Risks

- SQLite adapters can leak `sqlite3` errors or commit partial effects. Translate
  exceptions and test atomic boundaries at the port.
- Filesystem paths can accidentally become public identity. Keep path ownership
  in the host and derive blob identity only from bytes.
- A sync adapter may drift from async behavior. Run both through the same
  fixture suite and compare serialized results.

## Definition of done

- All listed ports are importable from `study_agent.api.storage` and are
  provider-neutral protocols.
- SQLite, filesystem, and memory implementations pass the same contract kit.
- Event replay and blob identity are deterministic; operational stores are
  visibly non-canonical.
- Adapter exceptions map to PF-02 failures and no path/credential leaks occur.
- Focused contract, integration, lint, and diff checks pass.
