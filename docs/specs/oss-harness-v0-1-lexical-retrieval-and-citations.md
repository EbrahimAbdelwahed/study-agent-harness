# Feature Spec: OSS Harness v0.1 Lexical Retrieval and Citations

Status: Implemented
Owner: Ebrahim / Codex orchestrator
Date: 2026-07-11

Implementation review: [`../reviews/20260711-oss-harness-v01-batch4.md`](../reviews/20260711-oss-harness-v01-batch4.md)
Run ID: `20260711-oss-harness-v01-batch4`
Parent spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Goal

Build a discardable SQLite FTS5/BM25 retrieval adapter over immutable source chunks and resolve every result to exact canonical normalized-text citations without leaking SQLite or framework types into public contracts.

## Problem

The harness can ingest and replay stable source spans but cannot search or resolve citations. Grounded-answer behavior requires a portable evidence set whose source/revision/chunk locators are independently verifiable against canonical content.

## In Scope

- Event-backed per-course `SourceContentPort` implementation over `EventStore` and `BlobStore`.
- Exact normalized-text loading and citation/subspan resolution with integrity checks.
- Provider/framework-neutral `RetrievalDocument` contract carrying course, immutable chunk, text, title, source kind/role/trust, and current-revision status.
- SQLite FTS5 `unicode61` index with BM25 ranking and derived metadata table.
- Idempotent indexing/upsert; changed current revision marks earlier source revisions superseded without deleting immutable documents.
- Query filters for course, selected revisions, source kinds, roles, minimum trust, and superseded revisions.
- Safe literal query compilation; source text and query syntax remain untrusted data.
- Stable deterministic tie-breaking and exact citations/snippets.
- `insufficient` when no lexical candidates survive filters; `sufficient` when candidates exist. Semantic conflict remains a later grounding-validator outcome.
- Contract, integration, injection, corruption, and citation mapping fixtures.

## Out of Scope

- Vectors, embeddings, reranking, PageIndex, knowledge graphs, semantic entailment/conflict detection, model calls, prompts, answer generation, HTTP/MCP, or product work.
- Mutating canonical event/blob state from retrieval.
- SQLite row IDs, FTS query objects, or SQL details in public results.

## Domain Model

- `RetrievalDocument`: immutable index input with canonical text and source metadata.
- `RetrievalQuery`: adds source-kind/role and superseded-revision filters.
- `RetrievalEvidence`: exact chunk, full-span citation, canonical text, and normalized portable score.
- `CourseSourceContent`: port adapter that validates event/blob commitments before resolving text.

## API / Interface Contract

- `SourceContentPort.get_text(revision_id)` and `resolve(citation)` operate within one configured course and fail explicitly for missing, mismatched, corrupt, or out-of-chunk spans.
- `RetrievalPort.index(documents)` accepts no SQLite/framework object.
- `RetrievalPort.search(query)` returns immutable evidence only.
- Index construction may be deleted/rebuilt without affecting domain truth.

## Prompt Behavior

- No prompt/model behavior.
- Prompt-injection strings are indexed and returned verbatim as untrusted evidence; they cannot alter SQL, tools, filters, or control flow.

## RAG / Source Grounding

- Citation source/revision/chunk and character offsets are mandatory.
- Quoted snippets are generated from canonical normalized content, never trusted from index rows or model input.
- Retrieval availability is not misrepresented as semantic entailment.

## Risks

- FTS query syntax injection or accidental broad queries.
- Searching superseded revisions by default and returning duplicate historical evidence.
- BM25 score direction/scale leaking adapter semantics.
- Stale/tampered index text producing citations not backed by canonical blobs.
- Citation offsets escaping their declared chunk.

## Acceptance Criteria

- [x] Event-backed content lookup returns exact canonical normalized text and detects missing/corrupt blobs.
- [x] Citation resolution rejects source/revision/chunk mismatch, out-of-chunk spans, and incorrect quoted snippets.
- [x] FTS search filters by course, revision, kind, role, trust, and current/superseded status before limiting.
- [x] Results are deterministic and carry resolvable exact citations/snippets.
- [x] Default search excludes superseded revisions.
- [x] Literal punctuation/quotes/operators and prompt-injection strings cannot change query/control semantics.
- [x] Empty matches return `insufficient`; candidates return `sufficient`; adapter does not invent semantic conflict.
- [x] Index deletion/rebuild produces equivalent public results.
- [x] Default tests require no network, provider SDK, model, Tau, or RAG framework.
- [x] Full pytest, Ruff, mypy, Flywheel, and semantic review gates pass.

## Verification

- Unit: query compilation, filters, score normalization, deterministic ordering, citation bounds.
- Contract: reusable retrieval and source-content behavior suites.
- Integration: ingest two sources/two revisions, index, filter, search, resolve, corrupt/rebuild.
- Evals: fixed lexical queries with expected source/revision/chunk IDs and insufficient cases.
- Manual: inspect one medical Markdown search and exact quoted spans.

## Open Questions

- none

## Task Beads

- `source-content-resolver`: event/blob-backed canonical text and citation resolution.
- `fts-retrieval`: portable retrieval contracts and SQLite FTS5/BM25 adapter.
