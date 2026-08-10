# Worker Brief: PF-04

## Assignment

Implement `PF-04` from `specs/package-foundation/slices/PF-04-storage-contract-kit.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01 through PF-04 slices, and `specs/package-foundation/beads/PF-04-storage-contract-kit.md`
- existing ports, SQLite/filesystem adapters, and storage contract tests

## Scope

You may change:

- `src/study_agent/api/storage.py`, `src/study_agent/ports/storage.py`, `ports/clock.py`, `ports/id_factory.py`
- `src/study_agent/adapters/sqlite/event_store.py`, `adapters/sqlite/run_store.py`, `adapters/filesystem/blob_store.py`, and scoped memory adapters
- `tests/contract/storage/**`, `tests/contract/event_store/**`, `tests/contract/blob_store/**`, `tests/contract/run_store/**`
- named storage integration tests

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, product files, event envelope semantics, source/capability/artifact/runtime behavior, CLI/UI, hosted persistence, or dependencies

## Invariants and Requirements

- Publish typed `EventStore`, `BlobStore`, `RunStore`, `Repository`, `Clock`, and `IdFactory` protocols with explicit Host composition.
- Event append uses expected sequence and idempotency; stale and changed-key requests fail without partial mutation.
- Blob refs are lowercase SHA-256 plus length; equal bytes deduplicate, mismatched bytes never overwrite, and reads verify checksum and length.
- Run records are operational CAS state and cannot write canonical learner facts. Clock returns aware UTC; IDs are deterministic under test factories.
- Run one parametrized fixture suite over memory, SQLite, and filesystem adapters and compare canonical serialized results byte-for-byte.
- Translate backend errors through PF-02 without exposing backend classes, paths, or credentials.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/storage tests/contract/event_store tests/contract/blob_store tests/contract/run_store
uv run --python 3.13 --extra dev pytest -q tests/integration/test_filesystem_blob_store.py tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py
uv run --python 3.13 --extra dev ruff check src/study_agent/ports src/study_agent/adapters/sqlite src/study_agent/adapters/filesystem tests/contract/storage
git diff --check
```

## Report Back

Return files changed, port/adapter/contract behavior, exact verification,
profile constraints followed, unresolved questions, and follow-up beads.
