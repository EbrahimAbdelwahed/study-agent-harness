# Task Bead: TUT-04C2 morphology-first anatomy implementation

Status: Done
Priority: P0
Type: expand
Depends On: TUT-04C0B2, TUT-04C0B1B

## Outcome

The anatomy profile produces isolated bundle-level object/region
reconstructions followed only by earned spatial or discriminating details while
retaining lesson-scale structure.

## Acceptance Criteria

- [ ] Closed role/family/cognitive-function contracts enforce reconstruction
  before details, at most three discriminations per macro, and contextual gaps
  only for compact relations/sequences.
- [ ] Each worker receives the compact whole-lesson index but grounds claims only
  in its active anatomy bundle; no tutor history, other raw lesson spans, or
  sibling-worker scratch output enters the prompt.
- [ ] The profile consumes exact `PreparedPlannedFlashcardScope` from the new
  private preparation binding; it never reconstructs trusted planner metadata
  from the unchanged legacy prepared scope or model output.
- [ ] Macro plans and details may use only planner-`eligible` topics in the
  active bundle. The model may omit an eligible topic but cannot elevate
  `context_only`, `excluded`, or globally indexed inactive topics.
- [ ] Checklist/answer blocks remain parallel, claims resolve to exact sources,
  and media require a trusted blob identity, digest, evidence link, and
  verification receipt.
- [ ] Non-anatomical/default selection, unearned atomization, spatial inversion,
  unverified media, Anki-shaped fields, overload, and prompt injection fail
  closed.
- [ ] There is no lesson or bundle card target. The existing 24-candidate bound
  is a transport/review ceiling; zero atomics and zero-card omitted bundles are
  valid outcomes.

## Verification

- Global-index/local-evidence and fresh-worker fixtures, object/topology/profile/
  relation cases, parent ratios, parsimony, media trust, grounding, injection,
  fallback, and prompt provenance.
