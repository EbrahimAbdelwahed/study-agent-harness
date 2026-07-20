# Task Bead: TUT-05E learner-evidence projection

Status: Done
Priority: P0
Type: expand
Depends On: TUT-05D

## Outcome

A pure replayable learner-evidence view summarizes effective grades by
assessment format and immutable rubric criterion while retaining the exact
supporting, contradicting, uncertain, contested, and superseded evidence.

## Acceptance Criteria

- [ ] The projection consumes canonical assessment history only. It emits no
  event and owns no tutor next-action, grading, recall, or scheduling policy.
- [ ] Because assessment artifacts do not yet carry a trusted concept ontology,
  the initial concept axis is a deterministic criterion key derived from exact
  artifact revision, criterion ordinal, and criterion text. A model-authored
  topic or inferred learner label never becomes the grouping key.
- [ ] Each estimate names its dimension/key/label, exact success
  numerator/denominator, `through_sequence`, and ordered evidence references
  containing both `GradeId` and canonical event sequence.
- [ ] Supporting, contradicting, uncertain, contested, and superseded evidence
  remain distinguishable. Only the uncontested active grade per attempt
  contributes to the effective ratio; history is never deleted.
- [ ] Estimates are deterministic without floating-point drift and rebuild
  byte-identically from the same event sequence.
- [ ] A separate `LearnerEvidenceViewPort` exposes this snapshot without
  breaking `TutorSnapshotV1`. TUT-06 composes both views in its external tutor
  host context.
- [ ] No event type, payload field, domain value, or projection state is named
  as a mastery update, and no global or cross-course learner aggregate exists.
- [ ] End-to-end replay covers accepted assessment artifact -> presentation ->
  attempt -> deterministic or verified grade -> contest -> verified superseding
  regrade -> identical evidence snapshot.

## Verification

- Projection and public-view contract tests; sequence/evidence golden fixtures;
  contested/superseded ratio cases; replay byte equality; explicit no-mastery
  and no-global-aggregate architecture tests; export/repository integration;
full offline gates.

## V1 ratio semantics

- Format estimates sum the exact `RationalScore` numerators and denominators of
  active uncontested grades.
- Criterion estimates use `1/1` for `met` and `0/1` for `not_met` or
  `uncertain`; the evidence category preserves the distinction.
- Superseded and contested grades remain ordered evidence but contribute `0/0`.
