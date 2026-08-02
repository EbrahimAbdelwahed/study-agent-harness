# Task Bead: TUT-07D recall integration closure

Status: Blocked on TUT-07C
Priority: P1
Type: closure
Depends On: TUT-07C

## Outcome

Repository composition, replay, public views, and export boundaries prove that
the optional recall capability is deterministic and that no exporter can own
or override canonical scheduling state.

## Acceptance Criteria

- [ ] Recall event registration is additive after artifact and assessment
  registration in repository, lifecycle-observer, and explicit export/replay
  composition; existing event, capability, and seven StudyTool fingerprints do
  not change.
- [ ] Deleting projections and replaying the same stream rebuilds identical
  review history, applied decisions, and due view without importing or invoking
  FSRS.
- [ ] Repository composition exposes recall only when the optional adapter is
  configured. Missing extras return one safe actionable availability result and
  never make unrelated repository commands fail.
- [ ] Public export uses a new explicitly versioned allowlist if recall records
  are included; old export versions remain byte-compatible and fail honestly on
  unsupported recall streams rather than silently dropping canonical state.
- [ ] Exported recall rows contain canonical review/schedule receipts only and
  exclude package objects, credentials, provider policy, local paths, raw
  traces, and mutable Anki scheduling fields.
- [ ] Architecture tests forbid Anki imports, deck/note ids, ease factors, and
  adapter-owned due state in canonical recall modules. Any Anki adapter consumes
  accepted artifacts and recall views and has no event-store write authority.
- [ ] End-to-end coverage proves accepted flashcard -> enrollment -> reviews ->
  applied FSRS decisions -> fake-clock due queue -> artifact supersession ->
  old revision removed -> replay-identical result.

## Verification

- Repository/replay/export integration; optional composition tests; Anki and
  import-boundary architecture tests; clean base and `[recall]` wheels; full
  offline suite, Ruff, strict mypy, `git diff --check`.
