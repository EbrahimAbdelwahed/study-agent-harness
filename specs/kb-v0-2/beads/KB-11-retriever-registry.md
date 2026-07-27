# KB-11: Retriever registry and candidate contract

Status: Implementation complete
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

- [x] `lex_projection` alone forms a functioning registry and search path.
- [x] Missing optional capabilities skip only their retriever with an explicit
  manifest reason.
- [x] Adding a conforming retriever requires registration, not caller/fusion
  code changes.
- [x] Candidate scores remain surface-local until fusion; adapter semantics do
  not leak into public evidence.
- [x] Registry order and candidate ties are deterministic.
- [x] Query/scope/filter data remains untrusted and cannot select arbitrary code.

## Verification

- Reusable retriever and registry contract suites.
- Duplicate/spoofed manifest, capability mismatch, oversized results, invalid
  ranks, and nondeterministic ordering tests.
- Architecture test that fusion imports only registry contracts.

## Review fixes

- Registry-owned manifest snapshots are detached from port-owned objects and
  all live manifests are revalidated before publishing a search batch.
- Search batches bind the exact registry fingerprint and complete manifest
  identity/fingerprint snapshot.
- Equal-score ordering covers non-adjacent recurring scores, and a public
  registry-size bound is enforced before manifest inspection.

## Out of scope

- RRF, context expansion, external adapters, or tool surfaces.
