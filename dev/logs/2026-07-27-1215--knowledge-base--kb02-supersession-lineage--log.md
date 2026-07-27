# Log: KB-02 source revision selection, succession, and lineage

Date: 2026-07-27 12:15
Area: knowledge-base

## Summary

Implemented KB-02. Revision selection is now readable as `current | inactive`,
cross-source succession is an explicit `source.superseded_by@1` event with
service authority, and a replayable lineage view exposes the original blob
chain, the substrate binding, and any declared successor without ever
migrating a citation.

## Files Changed

- `src/study_agent/domain/lineage.py`: new `SelectionStatus`, `RevisionRef`,
  `RevisionManifest`, `SourceSuccession`, `RevisionLineage`, `SourceLineage`.
- `src/study_agent/ingestion/succession.py`: new codec, reducer, and read
  contracts (`revision_selection_status`, `successor_of`, `revision_manifest`,
  `source_lineage`, `eligible_revision_ids`).
- `src/study_agent/ingestion/identity.py`: added
  `source_superseded_by_event_id_for`.
- `src/study_agent/ingestion/projection.py`: additive event registration.
- `src/study_agent/domain/__init__.py`: additive exports only.
- `tests/unit/knowledge/test_succession_lineage.py`: new (17 cases).
- `specs/kb-v0-2/beads/KB-02-supersession-lineage.md`,
  `specs/kb-v0-2/README.md`.

## Decisions

- `revision_id` keeps its existing v0.1 derivation. This bead defines the v0.2
  manifest field set and canonical encoding via `RevisionManifest.to_json`,
  but does not mint a second revision identity: ADR-0014 requires v0.2 to add
  versioned successors rather than mutate persisted contracts. Flagged for
  review in the bead and the README before KB-03 and KB-16 bind to it.
- Selection reuses `source.revision_selected@1` and `current_revision_id`.
  This bead adds only the read contract, so no second selection authority
  exists.
- Succession edges are an append-ordered array, not a map keyed by a composite
  string. A composite key needed a separator, and no separator is guaranteed
  absent from a source or revision identifier.
- `RevisionManifest.is_legacy_substrate` distinguishes a substrate bound by a
  `source.substrate_produced@1` receipt from one bound by the deterministic
  legacy mapping of a v0.1 normalized blob.

## Verification

- `pytest`: 2060 passed, 12 skipped (2043 before this change).
- `ruff check .` clean, strict `mypy` clean (489 files), `git diff --check`
  clean.
- Adversarial cases covered: self-link, missing endpoint on either side,
  conflicting successor, cycle, forged event identity, and non-service actor.
- Idempotence: an exact repeated succession returns the state unchanged.
- The lineage encoding is asserted to contain no timestamp, so no recency
  prior can leak into status or ranking.

## Deferred

- The lineage projection does not expose promoted study material. That edge
  needs the artifacts projection, whose ownership ADR-0014 does not assign to
  ingestion, and KB-13 owns the agent-facing read surface. Recorded in the
  bead under "Deferred" rather than silently dropped.

## Notes

- A literal NUL byte was accidentally written into `domain/lineage.py` while
  drafting a composite projection key; mypy caught it immediately and the
  composite key was removed in favour of the edge array described above.
