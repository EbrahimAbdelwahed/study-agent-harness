# Task Bead: source-revision-state Implement typed source-revision events and replayable projections

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch3`
Spec: `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`

## Worker Profile

create `source-state-worker`

Rationale:

No reusable specialization selected yet.

## Context

Immutable ingestion needs a fully validated event schema and projection shape before application code can append source revisions.

## What To Do

- Extend source domain contracts with normalized-text blob and normalization version while preserving provider-free immutability.
- Define source.revision_ingested@1 typed payload decoding and exact reducer registration.
- Validate revision/chunk IDs, blob metadata, stable spans, order, checksums, kinds, origins, and versions before persistence.
- Reduce immutable source manifests and chunks into deterministic projection state and add replay fixtures.

## Likely Files / Packages

- `src/study_agent/domain/source.py`: normalized content/revision contract additions
- `src/study_agent/ingestion/events.py`: typed ingestion event payload and decoder
- `src/study_agent/ingestion/projection.py`: source reducer registration and projection helpers
- `tests/unit/ingestion/`: payload and reducer tests
- `tests/integration/test_source_projection_replay.py`: SQLite replay proof

## Acceptance Criteria

- [ ] Malformed source/chunk payloads fail before event insertion.
- [ ] A valid ingestion event rebuilds byte-identical source/chunk projection state.
- [ ] Earlier revisions remain present when a later revision is reduced.
- [ ] No provider, retrieval, model, or direct projection-write behavior is introduced.

## Verification

- `.venv/bin/python -m pytest tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/domain/source.py src/study_agent/ingestion tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/domain/source.py src/study_agent/ingestion tests/unit/ingestion tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output

## Out Of Scope

- Blob writes, normalization, chunking algorithms, application service, retrieval, deletion, and migrations.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
