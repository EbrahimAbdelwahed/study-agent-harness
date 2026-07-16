# Task Bead: TUT-05 assessment and learner evidence

Status: Done
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

## Child Beads

1. [TUT-05A — canonical assessment ledger](TUT-05A-canonical-assessment-ledger.md)
2. [TUT-05B — deterministic closed grading](TUT-05B-deterministic-closed-grading.md)
3. [TUT-05C — provider-neutral free-text grading](TUT-05C-provider-neutral-free-text-grading.md)
4. [TUT-05D — verified free-text grade commit](TUT-05D-verified-free-text-grade-commit.md)
5. [TUT-05E — learner-evidence projection](TUT-05E-learner-evidence-projection.md)

TUT-05A becomes dependency-ready when TUT-04 closes. The remaining beads are
strictly sequential so the canonical event contract is stable before behavior,
verified model execution, and projections are added.

## Verification

- Ordering/CAS, prompt eval, grounding, adversarial grade, projection replay,
  full gates.
