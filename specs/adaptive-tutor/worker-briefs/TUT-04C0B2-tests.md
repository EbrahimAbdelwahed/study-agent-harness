# Worker Brief: TUT-04C0B2 lesson worker fan-out tests

## Goal

Independently pin exact active-evidence resolution, stable B1 delegation,
process-loss recovery, ordering, and compact/detail isolation for the B2
coordinator.

## Allowed Files

- `tests/unit/flashcards/test_lesson_worker_contracts.py`
- `tests/unit/flashcards/test_lesson_worker_service.py`
- `tests/unit/tools/test_planned_flashcard_scope_bridge.py`
- `tests/integration/test_lesson_worker_recovery.py`
- `tests/architecture/test_lesson_worker_boundaries.py`

## Forbidden Files

- Production, specs/docs, existing tests, adapters, dependencies, provisional
  C1/C2 files, and `sbobby-web`.

## Acceptance Criteria

- Exact codecs/fingerprints reject unknown fields, non-canonical bytes, changed
  plan/profile/request/authority, forged page positions or identities, duplicate
  pages, invalid transitions, oversized stored wrappers, an 8 MiB+ aggregate
  checkpoint (`lesson_worker_checkpoint_limit_exceeded`), and 257+ pages.
  No-work plans complete with zero port calls.
- Request fixtures require the sorted, complete, no-extra revision-id to
  content-SHA tuple for every plan span. Missing/duplicate/extra/reordered
  revisions, forged content fingerprints, resolver-observed fingerprint drift,
  and identities/checkpoints that omit these commitments fail closed.
- Resolver fixtures prove ordered one-slot-to-one-evidence construction at 1 and
  24 items. Missing/extra/reordered/merged/split/overlapping items, citation
  source/revision/offset/locator drift, insufficient/conflicting envelopes,
  duplicate handles, stale read-set fingerprints, and 25 items fail before B1.
- Prepared scope fixtures pin the full compact C0A index, active-topic-only
  handle links, active evidence only, exact wrapper plan/bundle/classification
  commitments, and byte-for-byte unchanged legacy scope behavior.
- The private tool accepts only the construction-bound query/scope and exact
  wrapper, rejects changed/extra arguments, and remains absent from the seven
  public StudyTools. It does not expose authority or accept a caller-supplied
  wrapper at invocation time. Tests do not pass context to `invoke`; a recording
  planned-worker adapter proves authority/context is checked before executor
  construction.
- `ProfileTaskExpectation` fixtures pin and fingerprint exact profile,
  capability/manifest, authority, complete pins, definition, output schema plus
  fingerprint, and ordered validation expectations. Mutating each returned B1
  task field independently fails before delegation.
- Recording profile/B1 ports prove exact public payload, deterministic task id,
  exact profile/prompt/skill/playbook/model/state/tool/validator/schema pins,
  plan+bundle+wrapper index references, ordered evidence references, and one
  B1 path only. Any returned-task mismatch fails before delegation.
- Public-signature fixtures/type checks pin the exact coordinator, review,
  resolver, binding, store, and `PlannedBundleWorker.detail ->
  VerifiedFlashcardPageResult` boundary. The coordinator never imports artifact
  owners or hand-parses candidate output; a recording adapter returns sanitized
  counts/commitments plus the verified one-page detail.
  resolver, profile binding, planned worker, and atomic store calls specified by
  the production brief. The structured continuation object transforms to exact
  canonical compact `continuation_summary_json`; non-canonical strings cannot be
  supplied, and profile/preferences never leak into the public payload.
- Multi-bundle fixtures cover concurrency 1 and greater than 1 with deliberately
  reversed completion order; compact receipts, page counts, and review positions
  remain canonical plan order. Repeated `advance` calls while the first children
  report running prove the global in-flight count never exceeds the configured
  cap and only freed capacity is claimed. Tests assert no synthetic overview and no lesson
  candidate target/minimum.
- Inject process loss at every recovery boundary: before/after resolution CAS,
  prepared scope persistence, child claim, B1 start, B1 terminal, and page CAS.
  A prepared retry does not resolve again; a completed page does not resolve or
  delegate again; a claimed child retries byte-identical B1 identity; CAS races
  either return identical state or conflict. Exact retry remains deterministic.
- Running child state remains in progress. Unexpected suspension and terminal
  cancelled/stale/failed/terminated states never yield lesson success or review
  detail. Changed plan/source/profile/task/authority on retry fails closed.
- Completed output is decoded through `FlashcardCandidateBatch`, respects the
  request ceiling, and records only compact counts/fingerprints. Compact views
  contain no candidate/evidence text, wrapper bytes, principal/session/provider
  data, or scratch output. Authorized page review returns one verified page;
  another authority or failed/incomplete page cannot read it.
- Architecture tests forbid direct dispatcher/gateway/playbook engine/model/
  validator/provider/event/artifact imports in the coordinator, forbid public
  tool registration and canonical writes, and preserve exactly seven StudyTools.

## Verification

Run the focused command from the production brief, then Ruff and strict mypy on
these five test files, relevant architecture/tool parity, full offline tests if
practical, and `git diff --check`.

## Report

Report production mismatches only; do not edit production, commit, or delegate.
