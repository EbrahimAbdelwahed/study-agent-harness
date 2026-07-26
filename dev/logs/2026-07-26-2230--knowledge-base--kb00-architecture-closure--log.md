# Log: KB-00 architecture closure

Date: 2026-07-26 22:30
Area: knowledge-base

## Summary

Closed KB-00 with ADR-0014. The decision separates revision-local occurrence
identity from cross-revision derived-work reuse, preserves v0.1 persisted
contracts through versioned successors, and pins replay, admission, connector,
and package ownership boundaries before runtime implementation.

The parent specification and bead graph now reflect those decisions. KB-01 is
the first dependency-ready implementation bead.

## Files Changed

- `docs/decisions/ADR-0014--kb-v02-identity-compatibility-and-replay.md`:
  accepted identity, compatibility, replay, and ownership decisions.
- `docs/specs/kb-v0-2-retrieval-architecture.md`: corrected the approved
  architecture.
- `specs/kb-v0-2/README.md`: activated the implementation graph and marked
  KB-00 complete.
- `specs/kb-v0-2/beads/KB-00-architecture-closure.md`: recorded closure.
- `specs/kb-v0-2/beads/KB-01-canonical-substrate.md`: marked the first bead
  ready with bounded worker contracts.
- `specs/kb-v0-2/beads/KB-10-scopes-manifest.md`,
  `specs/kb-v0-2/beads/KB-16-incremental-maintenance.md`, and
  `specs/kb-v0-2/beads/KB-19-exam-items-link-graph.md`: removed accidental
  dependencies on later optional connector or adapter work.
- `docs/worker-profiles/knowledge-base-core-worker.md` and
  `specs/kb-v0-2/worker-briefs/KB-01-*.md`: defined non-overlapping production
  and independent-test scopes.

## Verification

- Architecture review against existing v0.1 contracts: completed; conservative
  defaults incorporated.
- `git diff --check`: passed.

## Notes

- Runtime v1 retrieval migration happens at KB-13; its bridge is removed by
  KB-16 and verified absent by KB-23.
- Model/tool outputs are exact only while their content-addressed blobs are
  retained. Regeneration creates a new artifact receipt.
