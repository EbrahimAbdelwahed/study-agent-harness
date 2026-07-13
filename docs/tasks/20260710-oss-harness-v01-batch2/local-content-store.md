# Task Bead: local-content-store Implement immutable filesystem content-addressed storage

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260710-oss-harness-v01-batch2`
Spec: `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`

## Worker Profile

create `content-addressed-storage-worker`

Rationale:

No reusable specialization selected yet.

## Context

Text ingestion requires a local BlobStore that preserves original bytes immutably and exposes only validated content-addressed references.

## What To Do

- Implement FilesystemBlobStore against the existing BlobStore protocol with SHA-256 addressing and deterministic sharded paths.
- Use atomic temporary-file publication, fsync where practical, idempotent duplicate puts, and no replacement of existing content.
- Verify digest and byte length on every read and return explicit missing/integrity errors.
- Defend path derivation against traversal, symlinks, malformed references, and root escape.
- Add unit, contract, and temporary-filesystem integration tests.

## Likely Files / Packages

- `src/study_agent/adapters/filesystem/`: filesystem BlobStore implementation and errors
- `tests/contract/blob_store/`: reusable BlobStore behavior tests
- `tests/integration/test_filesystem_blob_store.py`: corruption, idempotency, and path-safety tests

## Acceptance Criteria

- [ ] Repeated puts of identical bytes return the same BlobRef and one immutable object.
- [ ] Get verifies checksum and length and reports missing/corrupt content explicitly.
- [ ] All object paths remain within the configured root and malformed references cannot traverse or follow attacker-controlled symlinks.
- [ ] Publication is atomic and cannot replace different bytes at a digest path.
- [ ] No dependency or provider/runtime type is introduced.

## Verification

- `.venv/bin/python -m pytest tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/adapters/filesystem tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/adapters/filesystem tests/contract/blob_store tests/integration/test_filesystem_blob_store.py`: expected to pass or produce documented output

## Out Of Scope

- Text extraction, source events, manifests, deletion, encryption, cloud stores, sync, and retrieval indexing.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
