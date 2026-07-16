# Task Bead: TUT-05A canonical assessment ledger

Status: Blocked on TUT-04
Priority: P0
Type: tracer-bullet
Depends On: TUT-04

## Outcome

Strict provider-neutral contracts and replay reducers record presented accepted
assessment items, immutable learner attempts, immutable grades, and human grade
contests in the per-course event stream without implementing grading behavior.

## Acceptance Criteria

- [ ] Distinct deterministic `PresentationId`, `AttemptId`, and `GradeId`
  values derive from trusted course/session/retry or target identities; model
  output and timestamps are never identity inputs.
- [ ] `assessment.item_presented@1` commits an accepted
  `assessment_item` revision, its exact content fingerprint, and a redacted
  learner delivery snapshot containing only format, prompt, and options.
- [ ] Presentation validation fails closed for a missing, proposed, rejected,
  superseded, wrong-kind, or fingerprint-drifted artifact revision. Expected
  response and evaluation criteria never enter the learner-facing view.
- [ ] Closed-answer encoding is unambiguous: single choice names exactly one
  listed option; multiple choice uses a canonical JSON array string of unique
  listed option texts and learner selections are stored in artifact order.
- [ ] `assessment.attempt_recorded@1` requires a prior presentation in the
  same course/session and stores one canonical response union, its fingerprint,
  and optional non-negative latency under HUMAN authority.
- [ ] `assessment.grade_recorded@1` requires a prior attempt and stores a
  strict result plus a closed deterministic-or-verified provenance union under
  SERVICE authority. An optional predecessor can supersede only a grade for the
  same attempt and never removes it.
- [ ] Deterministic grade provenance forbids model fields and binds a policy
  id/version/fingerprint plus rubric fingerprint. Verified capability
  provenance binds run, capability/proof, prompt/model/validator receipts, and
  the same rubric fingerprint without credentials or provider selection.
- [ ] `assessment.grade_contested@1` requires HUMAN authority, a prior grade,
  and an immutable reason. Contest and supersession history remain replayable.
- [ ] Exact codecs reject extra fields, cross-course/session references,
  duplicate commands, invalid authority, malformed fingerprints, secret-shaped
  values, and every attempt to record mastery, scheduling, or learner-model
  state.
- [ ] The projection exposes an internal full snapshot and a redacted learner
  presentation view. It owns no model, gateway, tool, UI, or provider behavior.
- [ ] Assessment registration is additive in canonical repository/replay/export
  composition and leaves the seven public StudyTools unchanged.

## Verification

- Value/codec/event/reducer/view unit tests; byte-identical replay; invalid
  ordering and authority fixtures; architecture imports; export/repository
  registration; Ruff; strict mypy; full offline gates.

## Worker Briefs

- [Production](../worker-briefs/TUT-05A-production.md)
- [Tests](../worker-briefs/TUT-05A-tests.md)
