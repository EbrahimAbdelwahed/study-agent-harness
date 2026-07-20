# Task Bead: TUT-04C0B2 lesson worker fan-out and recovery

Status: Done
Priority: P0
Type: expand
Depends On: TUT-04C0A, TUT-04C0B1

## Worker Profile

Reuse `grounded-study-artifact-worker`; use `test-engineer` for independent
process-loss and ordering fixtures.

## Outcome

A lesson-specific operational coordinator executes an immutable C0A plan
through injected isolated bundle-worker bindings and resumes without replaying
completed work.

## Acceptance Criteria

- [ ] The coordinator resolves each planned source-span slot to a bounded active
  evidence allowlist immediately before execution and rejects missing, drifted,
  overlapping, reordered, or more than 24 evidence slots/items. The request and
  resolver bind the canonical complete revision-id to content-fingerprint map;
  child identities and recovery checkpoints commit those exact bytes.
- [ ] Resolution constructs the new `PreparedPlannedFlashcardScope` from the
  unchanged `PreparedFlashcardScope` plus exact plan/bundle/topic/classification
  metadata and exposes it through a new private
  `source.prepare_planned_flashcard_scope@1` binding. It never widens or
  versions-in-place the existing preparation tool.
- [ ] It accepts an injected B1 child-run wrapper, derives stable child
  idempotency from plan/profile/bundle identity, and records ordered child run
  receipts in operational checkpoint state only.
- [ ] C0A v1 has no separately evidenced overview bundle, so B2 does not
  synthesize one or duplicate topic evidence. It executes the canonical C0A
  topic bundles only. Any future explicitly planned overview bundle must be a
  separately versioned planning change and complete before topic bundles.
  Topic-bundle concurrency is a bounded global in-flight setting across repeated
  coordinator advances; observed results and receipts are always ordered by the
  canonical plan rather than completion timing.
- [ ] Every child is started/resumed only through B1, which delegates one
  complete `propose_flashcards@1` skill/playbook run. B2 never invokes the
  dispatcher, playbook engine, or model port independently.
- [ ] Interruption resumes at the first incomplete bundle. Completed children are
  inspected and reused without repeating model, retrieval, or validator effects.
  Changed plan/profile/prompt/source fingerprints fail stale.
- [ ] One child output page retains the C0 24-candidate transport/review ceiling.
  The coordinator has no lesson card target/minimum and supports continuation
  across all planned bundles.
- [ ] Host-facing results expose only plan/run IDs, coverage, omissions, page
  counts, failures, and continuation state. Detailed candidate/evidence pages
  remain behind a typed lesson review view.
- [ ] The coordinator is event-state neutral, cannot accept/publish artifacts,
  adds no StudyTool, and does not change `propose_flashcards@1` manifest/output.

## Likely Files / Packages

- lesson coordinator/checkpoint/view modules under
  `src/study_agent/flashcards/` or `src/study_agent/application/`
- request-scoped composition helpers under capabilities only where needed
- focused recovery/integration/architecture tests

## Out of Scope

- Profile prompt semantics, cross-bundle semantic validation, artifact commit,
  exam analysis, UI, provider SDKs, hosted queues, and `sbobby-web`.

## Verification

- Ordered multi-bundle, bounded concurrency, overview-first, active-evidence
  resolution, process-loss at every boundary, exact retry, stale plan/source/
  profile, compact host/detail view separation, Ruff, strict mypy,
  architecture/tool parity, and full gates.

## Grilling Evidence

ADR-0010 plus the historical missing-continuation finding. This bead owns only
lesson fan-out/recovery; generic fresh-context execution belongs to B1.
