# KB-11: Retriever registry and candidate contract

Status: Proposed
Risk: High
Depends On: KB-09B, KB-10
Parent coverage: §§10.1–10.2; M5

## Outcome

Fusion discovers retrievers through a strict registry and consumes one portable
candidate shape without enumerating lexical, graph, vector, figure, or item
implementations.

## API seam

- `RetrieverManifest` declares identity/version, surface, cost, required
  capability, and default weight.
- `RetrieverPort.search()` returns bounded ranked candidates with unit identity,
  rank, adapter-local score, and provenance.
- Registry rejects duplicate identities, unsupported capabilities, mutable
  registration, and hidden network/model requirements.

## Acceptance criteria

- [ ] `lex_projection` alone forms a functioning registry and search path.
- [ ] Missing optional capabilities skip only their retriever with an explicit
  manifest reason.
- [ ] Adding a conforming retriever requires registration, not caller/fusion
  code changes.
- [ ] Candidate scores remain surface-local until fusion; adapter semantics do
  not leak into public evidence.
- [ ] Registry order and candidate ties are deterministic.
- [ ] Query/scope/filter data remains untrusted and cannot select arbitrary code.

## Verification

- Reusable retriever and registry contract suites.
- Duplicate/spoofed manifest, capability mismatch, oversized results, invalid
  ranks, and nondeterministic ordering tests.
- Architecture test that fusion imports only registry contracts.

## Out of scope

- RRF, context expansion, external adapters, or tool surfaces.
