# Plan: TUT-07D recall integration closure

Date: 2026-07-24 22:00 CEST
Area: adaptive-tutor / recall integration

## Goal

Compose the optional recall ledger into repository, lifecycle, replay, and
export paths without making FSRS or Anki part of canonical state. Add an
explicit export-v3 allowlist for canonical recall receipts while preserving v1
and v2 bytes and fail-closed behavior.

## Scope and ownership

- In scope: repository/lifecycle/event-registry composition, application
  export-v3 DTO/allowlist, filesystem v3 writer, recall composition/public
  availability, integration/replay/export/architecture tests, and this plan,
  log, and bead status updates.
- Out of scope: GAP/devkit/Flywheel, sbobby-web, provider/model adapters,
  Anki scheduling/export behavior, base StudyTools/capability identities,
  implicit FSRS imports, and dependency additions.

## Invariants

1. Recall registration is additive after artifact and assessment registration
   in every canonical composition path.
2. Canonical replay consumes recorded review/schedule receipts only; it never
   imports or invokes FSRS.
3. Recall is optional and unavailable composition is safe/actionable; unrelated
   base repository paths remain usable without the extra.
4. Export v1/v2 layouts and bytes remain unchanged. Export v3 is explicit and
   allowlists receipts only (no package objects, credentials, paths, traces,
   deck/note IDs, ease, or adapter-owned due state).
5. Exporters are read-only and never append to the event store.
6. Public export v3 has exactly one `recall.jsonl` allowlist. Review rows expose
   only `schema_version`, `receipt_type`, `course_sequence`, `session_id`,
   `review_id`, `revision_id`, `rating`, `latency_ms`, `confidence_bps`, and
   `occurred_at`. Schedule rows expose only the corresponding typed receipt
   fields: `schema_version`, `receipt_type`, `course_sequence`, `session_id`,
   `decision_id`, `revision_id`, `trigger`, `review_id`, `enrollment_at`,
   `due_at`, and policy/implementation/history/result fingerprints.
7. v1/v2 detect recall events before replay and fail exactly with
   `ExportStateError("recall export requires v3")`; they never register recall
   reducers. CLI accepts only versions 1, 2, and 3, defaulting to 1.
8. LocalRepository scheduler and scheduler-factory inputs are mutually
   exclusive in every constructor path; absent configuration is
   `NOT_CONFIGURED`, factory failure is safe `UNAVAILABLE`, and neither path
   appends canonical state during composition.

## Acceptance and verification

- Accepted flashcard -> enrollment -> review -> due view -> supersession ->
  replay produces identical recall state without scheduler execution.
- Missing/wrong optional adapter availability is typed and actionable.
- Focused composition/replay/export/architecture tests; full offline pytest,
  Ruff, strict mypy, base and recall wheel build, `git diff --check`.

## Implementation order

1. Inspect existing composition/export contracts and add minimal recall
   registration/composition seam.
2. Add explicit v3 bundle and atomic filesystem writer, preserving v1/v2.
3. Add integration and architecture regressions for replay, optionality,
   allowlist, and write authority.
4. Run focused gates, review diff semantically, update bead/parent status only
   for proven criteria, and commit a clean pass.

## Reviewer resolution

The architecture review required the explicit v3 field allowlist above, a
single recall file, no recall registration in v1/v2, exact legacy failure text,
and end-to-end real FSRS plus scheduler-free replay evidence in the recall CI
matrix. These constraints are now part of this worker contract.

## Evidence update

`tests/integration/test_recall_real_fsrs_e2e.py` now covers the real optional
adapter path (accepted flashcard, enrollment, review, due view, successor
supersession, projection rebuild, v3 export, and provider-free reopen). The
test is skipped only when the exact optional distribution is absent locally and
is explicitly run by the Python 3.12/3.13 recall CI job.
