# Task Bead: PF-05 Sources and citations

Status: Open
Priority: P1
Type: task
Depends On: PF-03, PF-04

## Outcome

Hosts can ingest immutable source revisions and resolve source-bound citations
from canonical bytes while keeping raw, normalized, citation, and derived
identities separate and replayable.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-05 source, revision, substrate, citation, lineage, and failure criteria in `specs/package-foundation/slices/PF-05-sources-citations.md`.
- README source-grounding, immutable identity, and opaque host-reference invariants.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-05-sources-citations.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `citation-resolution-worker`

Rationale:

The task is event-backed source and citation resolution with exact span/hash
checks, matching the existing profile and its corruption/ownership gates.

## Context

Grounded artifact and assessment contracts need canonical source evidence, not
retrieval snippets or model summaries. The source port owns bytes while Host
paths and educational authority remain outside Harness.

## Invariants

- `SourceId`, `RevisionId`, blob hash/length, normalized substrate, citation, and derived projection have separate identities and lineage.
- Public evidence names are `SourceEvidence`, `LearningEvidence`, `RetentionObservation`, and `CandidateWebEvidence`; bare `Evidence` is not public.
- `TextCitationV2` verifies source/revision/unit/substrate agreement, non-empty code-point bounds, and quoted SHA-256 against canonical bytes.
- Historical citations remain readable and supersession never rewrites the original citation; derived text cannot pass as primary evidence.
- Harness accepts bytes or a Host-owned input port and never scans arbitrary directories or admits live web content.

## What To Do

- Implement frozen source/revision/substrate/blob references and immutable revision creation.
- Implement citation v2 and figure citation codecs, minting, resolution, supersession status, and typed failure mapping.
- Preserve derived-reference lineage and explicit non-canonical status.
- Add equal-byte/new-byte, normalization, current/superseded, corrupt/out-of-unit, and replay/export fixtures.

## Likely Allowed Files / Packages

- `src/study_agent/api/sources.py`, `src/study_agent/domain/source.py`, `domain/citation_v2.py`.
- `src/study_agent/knowledge/citation.py`, `knowledge/projections.py`, `ports/source_input.py`.
- `src/study_agent/ingestion/identity.py`, `ingestion/service.py`, `adapters/filesystem/source_input.py`.
- `tests/contract/source_content/**`, `tests/contract/sources/**`, named integration tests, and citation unit tests.

## Acceptance Criteria

- [ ] Source/revision/blob/substrate/citation values are frozen, versioned, and importable from `study_agent.api.sources`.
- [ ] Equal bytes reuse identity, changed bytes create a new revision, and normalized substrate has independent identity.
- [ ] Citation resolution returns canonical text only after ownership, bounds, substrate, and quoted-hash checks; every failure maps safely.
- [ ] Current and superseded revisions resolve deterministically without rewriting historical citations.
- [ ] Derived references retain lineage but are rejected as primary evidence; replay/export is byte-stable.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/source_content tests/contract/sources tests/unit/knowledge/test_citation_v2.py`: contracts pass.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_source_content_resolution.py tests/integration/test_source_projection_replay.py tests/integration/test_text_ingestion.py`: integrations pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/domain/source.py src/study_agent/domain/citation_v2.py src/study_agent/knowledge src/study_agent/ingestion src/study_agent/api/sources.py tests/contract/sources`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Live web connectors, candidate brokers, cookies, credentials, arbitrary URL fetch, automatic admission, Cardine authority/currency/integrity, OCR/PDF/embedding dependencies, and new parser dependencies.

## Removal Conditions

- Remove legacy citation aliases after deterministic decoder/upcaster fixtures pass; no snippet-only verifier or second citation authority remains.

