# Task Bead: TUT-04D grounded exam-sample analysis

Status: Blocked on TUT-04A and TUT-03
Priority: P1
Type: expand
Depends On: TUT-04A, TUT-03

## Outcome

`analyze_exam_sample@1` turns trusted uploaded exam examples into a grounded
exam-blueprint proposal without grading a learner or claiming future certainty.

## Acceptance Criteria

- [ ] Output is a strict proposal describing observed formats, topic evidence,
  coverage, and uncertainty; no attempt, grade, mastery, or schedule is written.
- [ ] Every observation resolves to supplied exam-sample evidence; unsupported
  prediction and prompt injection fail closed.
- [ ] Capability is provider-neutral, has empty state writes, and cannot decide
  or publish its proposal.

## Verification

- Codec/prompt/validator, sparse/conflicting/injection fixtures, gateway eval,
  and full gates.
