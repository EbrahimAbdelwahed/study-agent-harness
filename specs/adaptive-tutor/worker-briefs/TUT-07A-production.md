# Worker Brief: TUT-07A production

## Goal

Implement the provider-neutral recall identities, strict event codecs, pure
reducers, projection-only views, and inward scheduling-policy port defined by
TUT-07A. Do not implement commands, due-query policy, or an FSRS adapter.

## Worker Profile

Use `recall-scheduling-worker`. Keep this worker limited to inward contracts,
event/reducer ownership, and the scheduler seam.

## Allowed Files

- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/recall.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/recall/__init__.py`
- `src/study_agent/recall/contracts.py`
- `src/study_agent/recall/events.py`
- `src/study_agent/recall/projection.py`
- `src/study_agent/recall/view.py`
- `src/study_agent/ports/scheduling.py`
- `src/study_agent/ports/__init__.py`

## Forbidden Files

- Tests; services; CLI/repository/export/lifecycle composition; adapters;
  `pyproject.toml`; lock files; FSRS, Anki, model, prompt, skill, playbook,
  capability, tool, tutor, artifact, assessment, or event-store implementation
  files; ADRs/specs; `sbobby-web`; and the seven StudyTools.

## Required Context

- TUT-07, TUT-07A, ADR-0004, and the completed TUT-04/TUT-05 contracts.
- Existing artifact lifecycle events/projection/view, assessment ledger strict
  codecs, per-course event registry, and canonical JSON/fingerprint patterns.
- An accepted `StudyArtifactKind.FLASHCARD` revision is the sole recall unit.
  Scheduling history belongs to its exact revision, not a mutable exporter card.

## Required Contracts

- Add typed `ReviewId` and `ScheduleDecisionId` plus deterministic derivation
  functions. Review identity uses trusted course/session/revision/retry inputs;
  the matching decision derives from enrollment or exact review identity.
  Timestamps, ratings, scheduler output, package objects, and model text never
  choose an id.
- Define a closed core `RecallRating` vocabulary with exactly
  `again | hard | good | easy`. This is not an imported package enum.
- Define strict frozen records for review history, schedule policy
  configuration, scheduling request, policy result receipt, review record,
  applied schedule, complete recall snapshot, and deterministic view rows.
- Represent confidence as optional integer basis points in `0..10000` and
  latency as optional non-negative integer milliseconds. Do not introduce
  canonical floats. All times are timezone-aware and normalized to UTC in
  codecs/views.
- The explicit v1 scheduling configuration contains only portable effective
  policy inputs needed by the adapter, including target-retention basis points,
  maximum interval days, ordered learning/relearning step minutes, and fuzzing
  disabled. It has exact codecs and a domain-separated fingerprint. Callers do
  not pass package names, versions, serialized weights, or opaque state.
- `SchedulingPolicyPort.decide(request) -> result` is the only inward scheduler
  seam. Its request contains exact revision id, enrollment time, complete
  ordered review history, and explicit configuration. Its result contains
  `due_at`, policy id/version/fingerprint, implementation id/version, history
  fingerprint, and result fingerprint only. No FSRS/Anki/card/log type crosses
  the protocol.
- Define exact schema-v1 codecs for:
  - `recall.review_recorded`: review/revision ids, rating, latency/confidence,
    idempotency key, and command fingerprint. Occurrence time is the trusted
    event-envelope time, not caller-authored payload data;
  - `recall.schedule_applied`: decision/revision ids, trigger kind
    `enrollment | review`, optional exact review id, enrollment time, due time,
    exact portable policy configuration, policy and implementation receipts,
    history/result fingerprints, idempotency key, and command fingerprint.
- Derive the complete history fingerprint from domain-separated canonical JSON
  containing schema version, exact revision, enrollment time, and every review
  in course-sequence order with review id, rating, latency, confidence, and
  occurrence time. Derive result fingerprint from the exact request/history,
  configuration/policy receipt, implementation receipt, and due time.
- Reducers validate against the already-replayed `study_artifacts` state. The
  target must exist and be `ACCEPTED` `FLASHCARD` at this event sequence.
  Initial schedule requires no prior recall state and empty history; review
  requires an enrollment; a review must be the sole pending history tail before
  its exact matching schedule; another review cannot arrive while one is
  pending. Decisions cannot skip, reorder, or bind another review/revision.
- Event authority is exact: HUMAN records reviews and SERVICE applies schedules.
  Registration helpers define recall reducers but this bead does not wire them
  into repository composition.
- Store a bounded `recall` projection section with immutable reviews, applied
  schedules, enrollment data, and command receipts. Preserve all historical
  decisions. Validate prior projection state before reduction and expose
  deterministic typed views; do not compute due eligibility in this bead.

## Security and Isolation Invariants

- Reject unknown/extra fields, malformed ids/fingerprints/times, non-finite or
  float confidence/latency, invalid history, wrong actor, and secret-shaped
  policy/implementation text.
- Reject keys or values that attempt to persist provider/model selectors,
  credentials, FSRS cards/logs/weights, Anki deck/note ids, ease factors,
  mutable package state, mastery updates, or global learner state.
- Inward recall/domain/port modules do not import adapters, CLI, storage,
  model/gateway, UI, provider SDK, `fsrs`, or Anki code.

## Acceptance Criteria

- Exact payload round trips are byte-identical, replay is pure, and malformed
  or impossible event order fails closed.
- A later artifact supersession does not delete prior recall history. TUT-07B's
  same-high-water due view owns filtering of no-longer-current revisions.
- This bead defines no command service, fake scheduler, FSRS adapter, due clock,
  export schema, or composition mutation.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing artifact, assessment, event-store, architecture, and public
  seven-tool contract tests.
- `git diff --check`

## Report

Report public names, exact event payloads, projection shape, scheduler DTOs,
commands/results, and any conflict with TUT-07A. Do not commit or delegate.
