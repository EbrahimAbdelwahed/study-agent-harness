# Task Bead: TUT-04C1 hybrid macro-detail implementation

Status: Ready
Priority: P0
Type: expand
Depends On: TUT-04C0B2, TUT-04C0B1B

## Outcome

The general hybrid profile turns each active lesson bundle into a parsimonious
framework-first proposal page while retaining the compact whole-lesson index.

## Acceptance Criteria

- [ ] Each generation call is a fresh isolated worker that receives the compact
  whole-lesson index, only its active contiguous bundle evidence, explicit
  learner preferences, and shape examples as untrusted data; it receives no
  tutor history or prior worker scratch output.
- [ ] The profile consumes exact `PreparedPlannedFlashcardScope` from the new
  private preparation binding. It does not infer bundle kind or planner
  eligibility from the unchanged legacy `PreparedFlashcardScope`.
- [ ] Overview generation, when planned, precedes bundle workers. Within a
  bundle, section frameworks precede linked earned details, and the worker
  assigns every active topic a model disposition of
  `generate|omit_scaffolding|omit`.
- [ ] Only planner-`eligible` active topics may be `generate`. The model may
  downgrade them to an omission, but can never elevate `context_only`,
  `excluded`, or globally indexed inactive topics into factual output.
- [ ] Validator enforces the closed model disposition, ordered
  overview/section/detail roles, detail-parent closure, non-overlap, uniqueness,
  grounding, and the technical per-page ceiling 24.
- [ ] Parsimony, not a numeric target, governs output: there is no lesson minimum
  or 16–22 default; framework cards exist only for recoverable structure and
  detail cards only for fragile/non-recoverable facts. Zero-card bundles and
  under-generation are valid when omissions are explicit.

## Verification

- Global-index/local-evidence separation, fresh-worker isolation, direct, sparse,
  zero-card, overlap, duplicate, per-page transport bound, source-gap, injection,
  fallback, and prompt provenance fixtures.
