# Task Bead: TUT-07A canonical recall ledger and scheduler port

Status: Blocked on TUT-05
Priority: P1
Type: tracer-bullet
Depends On: TUT-04, TUT-05

## Outcome

Strict provider-neutral values, event codecs, reducers, and an inward scheduler
port define immutable flashcard review history and applied scheduling decisions
without implementing commands or importing a scheduling package.

## Acceptance Criteria

- [ ] Deterministic `ReviewId` and `ScheduleDecisionId` values derive from
  trusted course/session/retry or trigger identities; time, package state, and
  scheduler output never choose canonical identity.
- [ ] The scheduler port accepts an exact accepted flashcard revision,
  enrollment time, ordered complete canonical review history, and explicit
  policy configuration; it returns only a normalized due decision and sanitized
  receipt.
- [ ] `recall.review_recorded@1` records revision identity, a closed FSRS-neutral
  rating vocabulary, optional non-negative latency, optional bounded
  confidence, occurrence time, retry identity, and command fingerprint.
- [ ] `recall.schedule_applied@1` records enrollment-or-review trigger,
  revision identity, exact portable policy configuration, due time, policy
  id/version/fingerprint, implementation id/version, history fingerprint,
  result fingerprint, and retry identity.
- [ ] The complete history fingerprint is domain-separated canonical JSON over
  the exact enrollment and ordered review inputs. Result fingerprint binds the
  request/history receipt to the exact due result.
- [ ] Reducers require an accepted `flashcard` revision at the event sequence
  where enrollment/review is applied, an empty history for initial enrollment,
  and exactly one new review before its matching schedule. No orphan review,
  duplicate enrollment, skipped review, or out-of-order decision is valid.
- [ ] Projection state preserves every review and applied decision; it never
  stores an `fsrs.Card`, library review log, opaque package state, Anki field,
  model behavior, or mutable due-only shortcut.
- [ ] Exact codecs reject extra fields, secret-shaped text, package/provider
  selectors, forged history/result fingerprints, wrong authority, malformed
  time/confidence/latency, and mastery/learner-model state.

## Verification

- Contract/value/event/reducer tests; byte-identical replay; import-boundary
  tests; existing artifact/assessment/tool contracts; Ruff; strict mypy.

## Worker Briefs

- [Production](../worker-briefs/TUT-07A-production.md)
- [Tests](../worker-briefs/TUT-07A-tests.md)
