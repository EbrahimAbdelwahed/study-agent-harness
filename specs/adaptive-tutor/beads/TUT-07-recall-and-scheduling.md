# Task Bead: TUT-07 recall and scheduling

Status: Refined; blocked on TUT-05
Priority: P1
Type: tracer-bullet
Depends On: TUT-04, TUT-05

## Worker Profile

create `recall-scheduling-worker`

## Outcome

Accepted flashcard revisions accumulate immutable review history and
reproducible due work through one provider-neutral scheduler port backed by the
publicly maintained `fsrs` Python package.

## Architecture Decision

- The canonical owner depends only on an inward scheduling-policy port and
  exact provider-neutral request/result DTOs. No `fsrs` type, serialized card,
  review log, module import, or implementation default crosses that seam.
- `fsrs==6.3.1` is an exact optional `recall` dependency, subject to install,
  API, conformance, and wheel verification in TUT-07C. The base harness keeps
  its zero-dependency install; hosts enable recall with
  `study-agent-harness[recall]`.
- Every applied decision records the policy id/version/fingerprint,
  implementation id/version, complete canonical history fingerprint, due time,
  and result fingerprint. Replay consumes the recorded result and never reruns
  FSRS.
- The scheduling identity is the exact accepted `ArtifactRevisionId`. A newly
  accepted successor starts a new schedule; carrying history across revisions
  would require a later explicit migration policy.
- Anki remains a downstream export/integration adapter. It cannot own review
  history, schedule state, due queues, or canonical identifiers.

## Acceptance Criteria

- [ ] Only currently accepted flashcard revisions can enroll, record reviews,
  or appear in a due queue; rejected, proposed, superseded, wrong-kind, and
  missing revisions fail or disappear deterministically.
- [ ] Reviews record outcome/rating, optional non-negative latency, optional
  bounded confidence, occurrence time, and exact revision identity as immutable
  canonical evidence.
- [ ] The first enrollment applies an empty-history schedule. Each later review
  and its next schedule append atomically in that order, so a review can never
  commit without its matching decision.
- [ ] Applied decisions pin policy and implementation versions, policy/history/
  result fingerprints, and due time. Exact retry converges; drift conflicts.
- [ ] Due queues rebuild without scheduler execution from canonical events,
  filter against current artifact acceptance at one projection high-water mark,
  compare with an injected clock, and sort by
  `(due_at, artifact_id, revision_id)`.
- [ ] The exact-pinned py-fsrs adapter passes the scheduler port conformance
  suite and golden fixtures. Missing optional dependencies fail with a safe,
  actionable composition error rather than breaking core imports.
- [ ] Anki and other exporters consume canonical views only and cannot write or
  override schedule state.

## Child Beads

1. [TUT-07A — canonical recall ledger and scheduler port](TUT-07A-canonical-recall-ledger.md)
2. [TUT-07B — authority-safe recall service and due view](TUT-07B-recall-service-and-due-view.md)
3. [TUT-07C — optional py-fsrs adapter](TUT-07C-py-fsrs-adapter.md)
4. [TUT-07D — replay, composition, and export isolation](TUT-07D-recall-integration-closure.md)

TUT-07A becomes dependency-ready after TUT-05 closes. The remaining beads are
sequential so canonical history and the inward seam stabilize before package
integration and release closure.

## Verification

- Exact codecs/reducer replay; scheduler port conformance and golden fixtures;
  review/schedule atomic CAS; fake-clock due queues; optional-install and
  import-boundary tests; export/Anki isolation; Python 3.12/3.13, Ruff, strict
  mypy, full offline gates.
