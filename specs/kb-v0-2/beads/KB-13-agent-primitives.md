# KB-13: Evidence packet and agent-facing primitives

Status: Done — offline evidence service and file-to-evidence proof verified 2026-08-01
Risk: High
Depends On: KB-03, KB-04, KB-10, KB-12
Parent coverage: §§10.4, 12–13; M5

## Outcome

The KB exposes narrow typed, model-free primitives and a fully provenance-bearing
`EvidencePacket` without adding a planner, synthesis layer, transport, or agent
SDK dependency.

## API seam

- `EvidenceRow`/`EvidencePacket` include canonical text, separate expansion,
  flags, revision status, figures, scores, retriever/projection provenance, and
  derived-content labels.
- Ports for `manifest`, `search`, `search_lexical`, `outline`, `unit`, `expand`,
  `resolve`, `figures`, `items`, `concepts`, and `lineage`.
- Each primitive has a bounded request/result and typed failure contract.

## Acceptance criteria

- [x] Every evidence row resolves through KB-03 before return.
- [x] `search_lexical` works offline with only structural projection and no
  optional capability.
- [x] Expansion has its own citation and never replaces the narrow citation.
- [x] Navigational `concepts` output is not represented as evidence.
- [x] Provenance permits callers to distinguish lexical versus derived/model
  discovery without trusting a model claim.
- [x] No primitive chooses what to teach, synthesizes an answer, or schedules
  work.
- [x] Existing v0.1 retrieval consumers have explicit compatible migration.

## Verification

- Public contract suite for every primitive and failure.
- Offline end-to-end ingest → project → search → expand → resolve → lineage.
- Architecture tests excluding UI, HTTP/MCP, agent SDK, model, and tutoring
  imports.

## Out of scope

- Wire formats, public tool registration, planner, or generated answers.
