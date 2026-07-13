# Task Bead: text-markdown-ingestion Implement deterministic text and Markdown ingestion

Status: Open
Priority: P1
Type: task
Depends On: source-revision-state
Run ID: `20260711-oss-harness-v01-batch3`
Spec: `docs/specs/oss-harness-v0-1-immutable-text-ingestion.md`

## Worker Profile

create `deterministic-ingestion-worker`

Rationale:

No reusable specialization selected yet.

## Context

With source event semantics fixed, the application service can preserve bytes, normalize text, construct stable chunks, and append one idempotent canonical revision event.

## What To Do

- Implement strict UTF-8 text/Markdown normalization with explicit version.
- Implement deterministic heading/paragraph-aware chunking and stable IDs/checksums.
- Implement TextIngestionService over BlobStore, EventStore, ClockPort, ExecutionContext, and source event contracts.
- Make unchanged ingestion idempotent and changed bytes produce a new revision.
- Add pure fixtures and filesystem-CAS/SQLite integration tests.

## Likely Files / Packages

- `src/study_agent/ingestion/normalization.py`: canonical UTF-8 normalization
- `src/study_agent/ingestion/chunking.py`: deterministic spans and identifiers
- `src/study_agent/ingestion/service.py`: application orchestration and structured results/errors
- `src/study_agent/ingestion/__init__.py`: explicit public surface
- `tests/unit/ingestion/`: normalization/chunking/id tests
- `tests/integration/test_text_ingestion.py`: CAS/event/replay/idempotency integration

## Acceptance Criteria

- [ ] Original and normalized bytes are immutable and checksummed.
- [ ] Every chunk span resolves exactly and deterministically into normalized text.
- [ ] Identical ingestion appends no duplicate event; changed bytes create a new revision.
- [ ] Invalid UTF-8/extension and sequence conflicts are explicit structured failures.
- [ ] No model, retrieval, provider, or direct projection mutation is introduced.

## Verification

- `.venv/bin/python -m pytest tests/unit/ingestion tests/integration/test_text_ingestion.py tests/integration/test_source_projection_replay.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/ingestion tests/unit/ingestion tests/integration/test_text_ingestion.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/ingestion tests/unit/ingestion tests/integration/test_text_ingestion.py`: expected to pass or produce documented output

## Out Of Scope

- PDF/OCR/audio, FTS, retrieval, citations, prompts, CLI, deletion, and distributed retries.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
