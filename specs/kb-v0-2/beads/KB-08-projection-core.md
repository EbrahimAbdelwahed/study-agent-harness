# KB-08: Index projection core and structural projector

Status: Proposed
Risk: High
Depends On: KB-05
Parent coverage: §§4, 5, 7–7.2; M3

## Outcome

Every unit can receive a versioned, deletable, non-citable searchable projection
through one projector port, starting with a deterministic structural projector.

## API seam

- `IndexProjection`, `ProjectionId`, `ProjectionRef`, `ProjectorManifest`, and
  `ProjectorPort` contracts.
- Projection store/read model is explicitly derived and separate from canonical
  unit/event state.
- Structural projector consumes unit plus ancestor headings and requires no
  model, key, or network.

## Acceptance criteria

- [ ] Handle, optional summary, terms, aliases, covers, structural context, and
  complete projector provenance have strict bounds and canonical encoding.
- [ ] Projection identity includes unit, projector name/version, and optional
  model identity exactly as resolved by KB-00.
- [ ] Deleting projections cannot make citations unresolvable.
- [ ] Structural projection is deterministic for every unit kind with a safe
  fallback for weak headings.
- [ ] Derived text is never exposed as canonical evidence.
- [ ] A projector upgrade invalidates only its derived outputs.

## Verification

- Public contract/codec tests and clean-room projector conformance suite.
- Delete/rebuild and provenance tests.
- Architecture tests blocking domain imports of provider adapters.

## Out of scope

- Corpus IDF, aliases, model projection, embeddings, or retrieval ranking.
