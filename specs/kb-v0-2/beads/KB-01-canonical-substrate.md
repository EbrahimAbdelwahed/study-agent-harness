# KB-01: Canonical substrate and provenance

Status: Ready
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
- Existing v0.1 text/Markdown events map through the substrate reducer without
  changing their payload or append behavior. New v0.2 revision construction is
  deferred to KB-02.

## Acceptance criteria

- [ ] Substrate ID is the SHA-256 of exact frozen normalized UTF-8 bytes.
- [ ] `SubstrateId` and production identity use the exact namespace, domain
  separator, canonical encoding, and identity fields fixed by ADR-0014.
- [ ] A substrate is non-empty normalized UTF-8. Pagination is either absent
  (`page_count=None`, empty map) or has a positive page count, an offset-zero
  first entry, strictly increasing in-bounds Unicode-code-point offsets, and
  strictly increasing positive pages bounded by the declared count.
- [ ] Converter, converter version, normalization version, original blob, and
  production time are recorded.
- [ ] Repeating the complete identity-bearing receipt is idempotent and retains
  the first committed `produced_at`. Changed converter, normalization,
  admission, or page-map policy creates a new production receipt; changed
  bytes create a new substrate. Old productions are never deleted.
- [ ] Invalid UTF-8, forged digests, bad page maps, and blob mismatches reject
  before event append.
- [ ] Projection deletion and replay reconstruct byte-identical metadata.

## Verification

- Unit codecs/identity/page-map tests.
- Integration with filesystem CAS and SQLite event store.
- Replay, append-conflict, orphan-blob, and corruption tests.

## Out of scope

- PDF conversion internals, tree parsing, unitization, retrieval, or GC.

## Worker Profile

Reuse `knowledge-base-core-worker`.

## Worker Briefs

- `../worker-briefs/KB-01-production.md`
- `../worker-briefs/KB-01-tests.md`
