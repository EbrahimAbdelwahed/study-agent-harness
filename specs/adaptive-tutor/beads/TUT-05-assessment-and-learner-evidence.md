# Task Bead: TUT-05 assessment and learner evidence

Status: Blocked on TUT-04
Priority: P0
Type: tracer-bullet
Depends On: TUT-02, TUT-04

## Worker Profile

create `assessment-evidence-worker`; use a prompt/eval specialist for
`grade_response@1` after the event contract is stable

## Outcome

Presented items, attempts, deterministic/grounded grades, and evidence-linked
learner projections support immediate adaptive tutoring.

## Acceptance Criteria

- [ ] Presented item commits before response; attempt commits before grade.
- [ ] Closed answers grade without a model.
- [ ] Free text returns graded, needs_review, or ungradable with rubric and provenance.
- [ ] Contest/supersession preserves prior grades.
- [ ] No mastery-update event exists; estimates name evidence and sequence.

## Verification

- Ordering/CAS, prompt eval, grounding, adversarial grade, projection replay,
  full gates.
