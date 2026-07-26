# KB-01: Canonical substrate and provenance

Status: Proposed
Risk: High
Depends On: KB-00
Parent coverage: §§4–4.1, 5.3, 13; M1

## Outcome

Frozen normalized-text substrates, page maps, production provenance, and their
canonical event can be stored and replayed without changing `BlobStore`
ownership or invoking a model.

## API seam

- Typed `SubstrateId`, substrate metadata, ordered `PageMapEntry`, production
  receipt, and strict codec.
- `source.substrate_produced@1` event and deterministic reducer/projection.
- Application service accepts trusted original-blob and converter receipts; it
  never accepts caller-authored hashes or provenance.
- Existing text/Markdown ingestion routes through the same substrate owner.

## Acceptance criteria

- [ ] Substrate ID is the SHA-256 of exact frozen normalized UTF-8 bytes.
- [ ] Page-map offsets are ordered, bounded, non-duplicated, and map only to
  valid pages.
- [ ] Converter, converter version, normalization version, original blob, and
  production time are recorded.
- [ ] Repeated exact production is idempotent; reconversion creates a new
  substrate record without deleting the old one.
- [ ] Invalid UTF-8, forged digests, bad page maps, and blob mismatches reject
  before event append.
- [ ] Projection deletion and replay reconstruct byte-identical metadata.

## Verification

- Unit codecs/identity/page-map tests.
- Integration with filesystem CAS and SQLite event store.
- Replay, append-conflict, orphan-blob, and corruption tests.

## Out of scope

- PDF conversion internals, tree parsing, unitization, retrieval, or GC.
