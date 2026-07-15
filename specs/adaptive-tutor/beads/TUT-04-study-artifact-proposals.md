# Task Bead: TUT-04 study artifact proposals

Status: In progress
Priority: P0
Type: tracer-bullet
Depends On: TUT-02

## Worker Profile

create `grounded-study-artifact-worker`; use `test-engineer` for independent
artifact lifecycle/provenance contracts

## Outcome

Versioned flashcard, assessment-item, exam-blueprint, and study-brief proposals
can be decided and revised with complete provenance.

## Child Beads

- [TUT-04A — artifact and pedagogical-profile contracts](TUT-04A-artifact-and-profile-contracts.md)
- [TUT-04B — canonical proposal and decision lifecycle](TUT-04B-canonical-artifact-lifecycle.md)
- [TUT-04C — grounded flashcard proposal capabilities](TUT-04C-grounded-flashcard-proposals.md)
- [TUT-04D — grounded exam-sample analysis](TUT-04D-grounded-exam-sample-analysis.md)
- [TUT-04E — verified commit and export integration](TUT-04E-artifact-integration.md)

## Acceptance Criteria

- [ ] Kind-specific codecs reject unknown or extra content.
- [ ] Generated content is a proposal, never implicit acceptance.
- [ ] Revisions retain prior artifact identity and source commitments.
- [ ] Only HUMAN or explicit trusted SERVICE policy decides acceptance.
- [ ] Export/replay retain deterministic artifact history without credentials.

## Verification

- Artifact lifecycle, provenance, RAG/source commitment, replay/export, full gates.
