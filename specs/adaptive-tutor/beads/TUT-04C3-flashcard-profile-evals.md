# Task Bead: TUT-04C3 profile gateway and adversarial evals

Status: In Progress (dependencies complete; lesson-wide aggregation contract remains)
Priority: P0
Type: contract
Depends On: TUT-04C0B2, TUT-04C1, TUT-04C2

## Outcome

The lesson coordinator composes planning, isolated profile workers, recovery,
and ordered aggregation through the gateway and exposes only verified pages plus
a compact tutor-facing summary.

## Acceptance Criteria

- [ ] Scripted end-to-end direct, retry, interruption, source drift, fallback,
  and injection cases retain prompt/validator/source provenance.
- [ ] `LessonFlashcardCoordinator` is an application/host service with its own
  typed receipt, compact summary view, and detailed review view. It internally
  asks B1 to start/resume child runs of the existing `propose_flashcards@1`
  gateway capability; it never invokes the gateway, playbook engine, or model
  directly and neither replaces nor changes the manifest, dispatcher, or output
  schema.
- [ ] A request-scoped composition root executes optional overview first and
  bounded bundle workers afterward, derives stable child retry identities, and
  resumes without repeating completed model/retrieval/validator effects.
- [ ] Every child has exactly one B1-wrapped skill/playbook run and exactly one
  profile-playbook `ModelStep`; no competing direct model path exists.
- [ ] Aggregation follows canonical lesson/bundle order, validates lesson-wide
  coverage, same-page parent linkage, and overview-to-bundle association metadata,
  and fails closed on cross-bundle duplicates,
  overlapping evidence, incompatible profiles, or unsupported candidates; it
  never silently fuzzy-deletes output.
- [x] The main tutor receives only plan/run IDs, coverage, omissions, page counts,
  failures, and continuation state. Detailed candidates and evidence are read
  through a typed review view rather than injected into tutor context.
- [ ] Profile selection cannot change under the same retry identity and no
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
  verification, and child-receipt cross-wire rejection.
- `tests/architecture/test_flashcard_capability_boundaries.py` proves the public
  seven-tool surface and ordinary capability registry remain unchanged.

## Remaining closeout gap

- The existing coordinator aggregates verified page counts and ordered review
  pages, but no lesson-wide candidate contract currently exposes enough typed
  metadata to verify cross-bundle duplicates, overlapping evidence,
  overview-to-bundle association, or whole-lesson coverage. The unchecked
  aggregation criterion must remain open until that contract exists; an eval
  cannot honestly infer those properties from counts or opaque detail payloads.
- Consequently the combined direct/retry/interruption/source-drift/fallback/
  injection matrix and the full profile-selection/output criterion remain open
  where they depend on lesson-wide verified candidate aggregation.
