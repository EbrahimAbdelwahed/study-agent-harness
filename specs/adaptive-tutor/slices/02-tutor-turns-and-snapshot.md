# Slice 02: Tutor turns and snapshot

## Outcome

General learner and tutor turns persist independently of grounded-answer
success, while one sequence-consistent snapshot composes course, context,
session, and materials without prescribing next action.

## Contract

- Existing session v1 replay remains valid.
- Assistant turns require a run and typed outcome references.
- Incomplete or cancelled output is never recorded as successful.
- Snapshot reports known, missing, and conflicting context with high-water
  sequence and evidence references.
- Immutable CourseProfile study fields are reported as configured hints with
  their own attribution. Disagreement with learner statements is visible and
  neither source silently wins.
- Capability advertisements are composed by the host after TUT-03; snapshot v1
  does not predeclare a gateway contract that does not yet exist.
