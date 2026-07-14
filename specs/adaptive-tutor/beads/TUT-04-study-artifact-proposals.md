# Task Bead: TUT-04 study artifact proposals

Status: Blocked on TUT-02
Priority: P0
Type: tracer-bullet
Depends On: TUT-02

## Worker Profile

create `grounded-study-artifact-worker`; use `test-engineer` for independent
artifact lifecycle/provenance contracts

## Outcome

Versioned flashcard, assessment-item, exam-blueprint, and study-brief proposals
can be decided and revised with complete provenance.

## Acceptance Criteria

- [ ] Kind-specific codecs reject unknown or extra content.
- [ ] Generated content is a proposal, never implicit acceptance.
- [ ] Revisions retain prior artifact identity and source commitments.
- [ ] Only HUMAN or explicit trusted SERVICE policy decides acceptance.
- [ ] Export/replay retain deterministic artifact history without credentials.

## Verification

- Artifact lifecycle, provenance, RAG/source commitment, replay/export, full gates.
