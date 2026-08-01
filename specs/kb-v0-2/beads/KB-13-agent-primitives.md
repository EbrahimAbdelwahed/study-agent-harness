# KB-13: Evidence packet and agent-facing primitives

Status: Partial — verified lexical evidence baseline; remaining agent primitive
surface is tracked as follow-up
Risk: High
Depends On: KB-03, KB-04, KB-10, KB-12
Parent coverage: §§10.4, 12–13; M5

## Outcome

The KB exposes narrow typed, model-free primitives and a fully provenance-bearing
`EvidencePacket` without adding a planner, synthesis layer, transport, or agent
SDK dependency.

## API seam

- `EvidenceRow`/`EvidencePacket` include verified canonical text, score, and
  lexical retriever/projection provenance.
- The offline baseline exposes bounded `search` and unit-id `resolve`; discovery
  is explicitly limited to `lex_projection` until richer provenance receipts
  are carried through fusion.

## Acceptance criteria

- [x] Every lexical evidence row resolves through KB-03 against canonical unit
  and substrate records before return.
- [x] Offline lexical search works with only structural projection and no
  optional capability.
- [x] Expansion has its own citation and never replaces the narrow citation.
- [ ] Ports and bounded contracts for `manifest`, `outline`, `unit`, standalone
  `expand`, citation-addressed `resolve`, `figures`, `items`, `concepts`, and
  `lineage`.
- [ ] Provenance receipts for derived/model retrievers through fusion.
- [x] No primitive chooses what to teach, synthesizes an answer, or schedules
  work.
- [x] Existing v0.1 retrieval consumers have explicit compatible migration.

## Verification

- Offline end-to-end ingest → project → search → verified evidence.
- Architecture tests excluding UI, HTTP/MCP, agent SDK, model, and tutoring
  imports.

## Out of scope

- Wire formats, public tool registration, planner, or generated answers.
- The remaining KB-13 primitive surface and non-lexical evidence receipts.
