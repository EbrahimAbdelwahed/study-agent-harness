# Task Bead: PF-04 Storage contract kit

Status: Open
Priority: P1
Type: task
Depends On: PF-01, PF-02, PF-03

## Outcome

Hosts can inject narrow storage, clock, and ID ports while memory, SQLite, and
filesystem adapters pass one offline contract kit for optimistic concurrency,
immutable blobs, replay equality, and safe adapter errors.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-04 ports, adapter, blob identity, replay, and contract-kit criteria in `specs/package-foundation/slices/PF-04-storage-contract-kit.md`.
- README canonical-stream, explicit-composition, and standard-library-only invariants.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-04-storage-contract-kit.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `content-addressed-storage-worker`

Rationale:

The bead centers on immutable content-addressed blobs, adapter safety, and
contract fixtures, matching the existing storage profile. Event-store work
also uses the event-state profile's quality constraints through the slice brief.

## Context

Later source, capability, artifact, and runtime slices need a provider-neutral
port boundary. Reference adapters must remain replaceable and operational
stores must never become canonical learner state.

## Invariants

- `EventStore`, `BlobStore`, `RunStore`, `Repository`, `Clock`, and `IdFactory` are typed protocols supplied by the Host.
- Event append validates expected sequence and idempotency before commit; stale and changed-key inputs never partially mutate state.
- Blob identity is lowercase SHA-256 plus length; equal bytes deduplicate, different bytes never overwrite, and reads verify integrity.
- Run records are operational and CAS-protected; they cannot write canonical learner facts.
- UTC-aware clocks and deterministic ID factories are testable without hidden global state; physical paths remain Host-owned.

## What To Do

- Publish storage protocols and typed result/error mappings through `study_agent.api.storage`.
- Implement or align memory, SQLite event/run, and filesystem blob adapters with atomic append/CAS and checksum verification.
- Build parametrized contract fixtures that compare canonical serialized results across adapters.
- Cover empty streams, stale/equal-key/changed-key paths, rollback, dedupe, corruption, CAS races, UTC, and replay equality.

## Likely Allowed Files / Packages

- `src/study_agent/api/storage.py`, `src/study_agent/ports/storage.py`, `ports/clock.py`, `ports/id_factory.py`.
- `src/study_agent/adapters/sqlite/event_store.py`, `adapters/sqlite/run_store.py`, `adapters/filesystem/blob_store.py`, and memory adapters.
- `tests/contract/storage/**`, `tests/contract/event_store/**`, `tests/contract/blob_store/**`, `tests/contract/run_store/**`, and named integration tests.

## Acceptance Criteria

- [ ] All six ports are importable, provider-neutral protocols and are composed explicitly.
- [ ] Memory and SQLite event stores preserve envelope sequence, idempotency, rollback, and typed stale/conflict errors.
- [ ] Filesystem and memory blob stores deduplicate equal bytes, reject mismatched checksums/lengths, verify reads, and never overwrite.
- [ ] Run-store CAS is atomic and visibly operational; replay from the same events is byte-identical across adapters.
- [ ] Adapter exceptions map to PF-02 failures without paths, credentials, or backend types in public values.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/storage tests/contract/event_store tests/contract/blob_store tests/contract/run_store`: contract kit passes.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_filesystem_blob_store.py tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py`: integrations pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/ports src/study_agent/adapters/sqlite src/study_agent/adapters/filesystem tests/contract/storage`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- JobStore, distributed queue, lease/retry worker, hosted persistence, path discovery, global repositories, Cardine layout, debug-data migration, or new dependencies.

## Removal Conditions

- Remove adapter-specific public exceptions, serializers, and path helpers; retain private compatibility only while named consumers migrate and canonical bytes remain single.

