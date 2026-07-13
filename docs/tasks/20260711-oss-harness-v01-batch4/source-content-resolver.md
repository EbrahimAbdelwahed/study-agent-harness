# Task Bead: source-content-resolver Implement event-backed canonical source and citation resolution

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch4`
Spec: `docs/specs/oss-harness-v0-1-lexical-retrieval-and-citations.md`

## Worker Profile

create `citation-resolution-worker`

Rationale:

No reusable specialization selected yet.

## Context

Retrieval and grounding need one port-neutral authority that maps immutable revision/chunk identifiers to verified normalized text and exact citation spans.

## What To Do

- Implement a per-course SourceContentPort over EventStore and BlobStore using typed source-event decoding.
- Load and verify normalized content commitments and immutable revision/chunk ownership.
- Resolve full or sub-chunk citations from canonical text and generate quoted snippets.
- Reject missing, corrupt, mismatched, out-of-bounds, or incorrectly quoted citations with structured errors.
- Expose immutable retrieval documents for current/all revisions without writing canonical state.

## Likely Files / Packages

- `src/study_agent/retrieval/content.py`: event-backed content/catalog adapter
- `src/study_agent/retrieval/errors.py`: structured resolution errors
- `src/study_agent/retrieval/__init__.py`: explicit public surface
- `tests/contract/source_content/`: source-content/citation behavior
- `tests/integration/test_source_content_resolution.py`: ingestion-to-resolution proof

## Acceptance Criteria

- [ ] Exact normalized text is returned only after blob/event validation.
- [ ] Every resolved citation lies inside its declared immutable chunk and returns canonical text.
- [ ] Wrong ownership, offsets, quote, missing revision, and corruption fail explicitly.
- [ ] Current/superseded revision document metadata is deterministic and event-derived.

## Verification

- `.venv/bin/python -m pytest tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/retrieval tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/retrieval tests/contract/source_content tests/integration/test_source_content_resolution.py`: expected to pass or produce documented output

## Out Of Scope

- FTS, ranking, model grounding, source mutation, HTTP/MCP, and product behavior.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
