# Feature Spec: OSS Harness v0.1 Immutable Text Ingestion

Status: Implemented
Owner: Ebrahim / Codex orchestrator
Date: 2026-07-11

Implementation review: [`../reviews/20260711-oss-harness-v01-batch3.md`](../reviews/20260711-oss-harness-v01-batch3.md)
Run ID: `20260711-oss-harness-v01-batch3`
Parent spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Goal

Ingest UTF-8 text and Markdown into immutable original and normalized content objects, emit typed source-revision events, and derive replayable source/chunk projections with stable character spans.

## Problem

The harness has authoritative event state and immutable blobs but no study content can enter the domain. Retrieval cannot be implemented until normalized text, source revisions, chunk locators, and their provenance are deterministic and replayable.

## In Scope

- Strict UTF-8 `.txt` and `.md` input only.
- Preserve original bytes in `BlobStore`; store normalized UTF-8 bytes separately when different.
- Deterministic newline/Unicode normalization and explicit normalization version.
- Deterministic heading/paragraph-aware chunking with explicit chunker version and stable offsets into normalized text.
- Deterministic source revision and chunk identifiers derived from immutable inputs and algorithm versions.
- Typed `source.revision_ingested@1` payload decoder and reducer.
- Event-derived source manifest and chunk projection data; no direct projection writes.
- Idempotent unchanged ingestion; changed bytes create a new immutable revision.
- Application service using `BlobStore`, `EventStore`, `ClockPort`, and trusted `ExecutionContext`.
- Structured results/errors and integration tests against filesystem CAS plus SQLite event store.

## Out of Scope

- PDF/OCR/audio, encodings other than UTF-8, vector embeddings, FTS, retrieval, citations, model calls, prompts, sessions, CLI, deletion, sync, or product work.
- Mutating or superseding prior revisions.
- Distributed/multi-writer retry policy beyond explicit sequence conflict.

## Domain Model

- `SourceDocument` gains an immutable normalized-text blob reference and normalization version.
- `SourceChunk` offsets always address the canonical normalized text and include the chunker version/checksum.
- `TextIngestionResult` returns the source document, chunks, emitted/idempotent status, and committed sequence.
- One typed ingestion event contains the complete immutable manifest required to rebuild projections.

## API / Interface Contract

- Pure normalization and chunking functions are independently testable.
- `TextIngestionService.ingest(...)` accepts trusted course/source metadata and bytes; callers cannot supply event sequence or epistemic metadata inconsistent with policy.
- Event IDs/revision IDs/chunk IDs are deterministic content-derived identifiers; the correlation ID and actor come from `ExecutionContext`; timestamp comes from `ClockPort`.
- The service stores blobs before event append. An append conflict produces an explicit retryable conflict without corrupting canonical state; orphan content-addressed blobs are harmless and reusable.

## Prompt Behavior

- No prompt or model behavior.

## RAG / Source Grounding

- Stable chunk offsets and checksums are release-blocking because later citations resolve against them.
- Chunk text is never trusted as instructions; ingestion performs no semantic/model transformation.
- Retrieval/indexing is a later batch over these persisted spans.

## Risks

- Unicode/newline normalization changing offsets nondeterministically.
- Markdown structure parsing becoming a full parser.
- Duplicate ingestion appending duplicate canonical events.
- Projection payloads omitting normalized blob/version data needed for future citation resolution.
- Event payload validation accepting malformed spans or mismatched checksums.

## Acceptance Criteria

- [x] Original bytes are preserved byte-for-byte and never overwritten.
- [x] Invalid UTF-8 and unsupported extensions fail before a domain event is appended.
- [x] Normalization is deterministic, versioned, and produces canonical UTF-8 text.
- [x] Chunking is deterministic, versioned, non-overlapping, ordered, and every span resolves exactly into normalized text.
- [x] Re-ingesting identical bytes/config is idempotent and appends no duplicate event.
- [x] Changed bytes create a new immutable revision while preserving the earlier revision.
- [x] Source event payload decoding validates IDs, blob metadata, offsets, ordering, and checksums before persistence.
- [x] Projection deletion/replay reconstructs byte-identical source/chunk state.
- [x] Default tests require no network, API key, provider SDK, or Tau.
- [x] Full pytest, Ruff, mypy, Flywheel, and semantic review gates pass.

## Verification

- Unit: UTF-8, normalization fixtures, Markdown headings/paragraphs, chunk boundaries, stable IDs, payload rejection.
- Integration: filesystem CAS plus SQLite event append/projection/replay; identical and changed re-ingestion.
- Evals: none; behavior is deterministic code.
- Manual: inspect one normalized medical Markdown fixture and its exact spans.

## Open Questions

- none

## Task Beads

- `source-revision-state`: source domain additions, typed event payload, reducer, replay fixtures.
- `text-markdown-ingestion`: deterministic normalization/chunking and ingestion service integration.
