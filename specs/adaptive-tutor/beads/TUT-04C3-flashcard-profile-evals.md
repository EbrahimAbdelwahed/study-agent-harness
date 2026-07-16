# Task Bead: TUT-04C3 profile gateway and adversarial evals

Status: Done
Priority: P0
Type: contract
Depends On: TUT-04C0B2, TUT-04C1, TUT-04C2

## Outcome

The lesson coordinator composes planning, isolated profile workers, recovery,
and ordered aggregation through the gateway and exposes only verified pages plus
a compact tutor-facing summary.

## Acceptance Criteria

- [x] Scripted end-to-end direct, retry, interruption, source drift, fallback,
  and injection cases retain prompt/validator/source provenance.
- [x] `LessonFlashcardCoordinator` is an application/host service with its own
  typed receipt, compact summary view, and detailed review view. It internally
  asks B1 to start/resume child runs of the existing `propose_flashcards@1`
  gateway capability; it never invokes the gateway, playbook engine, or model
  directly and neither replaces nor changes the manifest, dispatcher, or output
  schema.
- [x] A request-scoped composition root executes optional overview first and
  bounded bundle workers afterward, derives stable child retry identities, and
  resumes without repeating completed model/retrieval/validator effects.
- [x] Every child has exactly one B1-wrapped skill/playbook run and exactly one
  profile-playbook `ModelStep`; no competing direct model path exists.
- [x] Aggregation follows canonical lesson/bundle order, validates lesson-wide
  coverage, same-page parent linkage, and overview-to-bundle association metadata,
  and fails closed on cross-bundle duplicates,
  overlapping evidence, incompatible profiles, or unsupported candidates; it
  never silently fuzzy-deletes output.
- [x] The main tutor receives only plan/run IDs, coverage, omissions, page counts,
  failures, and continuation state. Detailed candidates and evidence are read
  through a typed review view rather than injected into tutor context.
- [x] Profile selection cannot change under the same retry identity and no
  generated output contains decisions or canonical artifact IDs.
- [x] Shared seven-tool and existing capability contracts remain unchanged.
- [x] The coordinator adds no public StudyTool. Exposing it later as a public
  capability requires a new versioned contract and ADR, not a silent C0 change.

## Verification

- Lesson-plan/fan-out/resume/aggregation fixtures, gateway/eval/architecture/full
  offline gates.

## Verified evidence

- `tests/evals/test_lesson_flashcard_profile_coordination.py` composes the real
  hybrid and morphology task bindings with the lesson coordinator. It proves
  stable child task/scope bytes across retry, one pinned profile playbook model
  step, private selection receipts outside public task input, and fail-closed
  source/profile drift even when query/scope text attempts prompt injection.
- `tests/unit/flashcards/test_lesson_worker_service.py` proves persisted
  prepare/claim recovery, stable child identities, bounded fan-out, canonical
  page order, terminal failure handling, compact/detail separation, task-field
  verification, and child-receipt cross-wire rejection. Its completed-lesson
  review fixtures also prove strict candidate-batch decoding, canonical page
  order, page-scope evidence ownership, lesson-wide candidate-key uniqueness,
  and the cross-page canonical-span overlap predicate.
- `tests/architecture/test_flashcard_capability_boundaries.py` proves the public
  seven-tool surface and ordinary capability registry remain unchanged.

## Aggregation closeout

- `LessonWorkerCompletedReviewView` now exposes exact-decoded batches to an
  authorized reviewer without changing the compact tutor view. The service
  fails closed on cross-page candidate-key duplicates, cross-page overlapping
  canonical evidence spans, evidence handles outside the owning page, count
  drift, failed/incomplete pages, and invalid batch shapes.
- Whole-lesson topic coverage is derived without exposing the profile-private
  `topic_plan`: each active topic's prepared evidence handles must intersect
  evidence cited by at least one candidate on that page. Omissions do not count
  as candidate coverage and therefore fail closed with a stable incomplete-
  coverage conflict.
- Optional overview association is derived from the existing candidate
  `OVERVIEW` role. At most one may exist lesson-wide, it must occur on the
  earliest canonical page, and its typed association names all other canonical
  page positions and bundle IDs. No new `PlannedBundleKind`, cross-page parent
  edge, or inferred overview is introduced; lessons without an overview expose
  an empty association tuple.
- Consequently the combined direct/retry/interruption/source-drift/fallback/
  injection matrix and the full profile-selection/output criterion remain open
  where they depend on lesson-wide verified candidate aggregation.
