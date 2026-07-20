# Slice 05: Assessment and learner evidence

## Outcome

Presented items, immutable attempts, and versioned grades produce deterministic
evidence projections by concept and assessment format.

## Contract

- Item content/fingerprint commits before the learner response.
- Attempt commits before grading.
- Closed-answer grading is deterministic.
- The versioned grading procedure may return graded, needs_review, or ungradable and carries
  rubric, citations, confidence, validators, and model provenance.
- Its `grade_response@1` gateway manifest is registered only after TUT-03 and
  is integrated by TUT-06.
- Grades may be contested or superseded; estimates are projections, not events.
