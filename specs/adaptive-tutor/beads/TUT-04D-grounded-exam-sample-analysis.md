# Task Bead: TUT-04D grounded exam-sample analysis

Status: Done
Priority: P1
Type: expand
Depends On: TUT-04A, TUT-03, TUT-04C0B1, TUT-04C0B1A

## Outcome

`analyze_exam_sample@1` turns trusted uploaded exam examples into a grounded
exam-blueprint proposal without grading a learner or claiming future certainty.

## Acceptance Criteria

- [x] Output is a strict proposal describing observed formats, topic evidence,
  coverage, and uncertainty; no attempt, grade, mastery, or schedule is written.
- [x] Every observation resolves to supplied exam-sample evidence; unsupported
  prediction and prompt injection fail closed.
- [x] Analysis executes as a fresh isolated worker with an allowlisted exam-task
  envelope. Tutor history, unrelated materials, sibling generation drafts,
  credentials, and principal data never enter its prompt; the tutor receives a
  compact observed-coverage/uncertainty summary and reads details through a typed
  proposal view.
- [x] Start/detail deterministically rebuild the task from the typed request and
  opaque request key; proof reads use B1's public child-context derivation and an
  injected exam proof-reader protocol, never task-id lookup or duplicated
  authority/context logic.
- [x] Capability is provider-neutral, has empty state writes, and cannot decide
  or publish its proposal.

## Verification

- Codec/prompt/validator, worker-isolation, sparse/conflicting/injection fixtures,
  gateway eval, and full gates.
