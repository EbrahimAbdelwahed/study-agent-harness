# Worker Brief: TUT-04C0B2 lesson worker fan-out

## Goal

Implement the provider-neutral operational coordinator that resolves every C0A
bundle into an exact planned scope, delegates it through the B1 worker boundary,
and resumes after process loss without repeating completed child effects.

## Allowed Files

- `src/study_agent/flashcards/lesson_worker_contracts.py`
- `src/study_agent/flashcards/lesson_worker_service.py`
- `src/study_agent/flashcards/lesson_worker_view.py`
- `src/study_agent/ports/lesson_worker.py`
- `src/study_agent/tools/planned_flashcard_scope_bridge.py`

## Forbidden Files

- Existing files and package exports, C0A planning and B1 worker modules,
  prompts/skills/playbooks/profile implementations, capability dispatcher or
  gateway, model/provider adapters, artifact/event/state owners, CLI,
  configuration, dependencies, tests, specs/docs, provisional C1/C2 files, and
  `sbobby-web`.

## Required Contracts

- Define strict immutable `LessonWorkerRequest`, operational checkpoint/page
  receipt values, compact run view, and one-page-at-a-time typed review view.
  The request binds the exact `FlashcardLessonPlan`, public flashcard query,
  non-null scope, language, candidate ceiling `1..24`, canonical nullable
  structured continuation-summary object, profile-task expectation, concurrency
  `1..8`, and a canonical complete tuple of
  `(revision_id, content_fingerprint)` commitments. The revision tuple is sorted
  by revision id, contains exactly every distinct revision named anywhere in the
  plan and no other revision, and every content fingerprint is lowercase
  SHA-256. Its exact bytes are part of the request fingerprint.
  It contains no authority, provider selector, credentials, tutor history,
  artifact decision, or desired lesson/card count.
- Define inward protocols for: (1) exact planned-slot evidence resolution, (2)
  a profile-pinned B1 task binding, (3) a planned-bundle worker that accepts the
  exact prepared wrapper and delegates start/detail to B1, and (4) atomic
  operational create/CAS/load. The coordinator may call only these ports. It
  must not import or invoke the dispatcher, gateway, playbook engine, model, or
  validators. C1/C2/C3 will provide concrete profile composition later.
- Pin these public signatures exactly (names may be implemented in the listed
  owner modules, but argument meaning and return types must not drift):
  `LessonWorkerService.start(request, parent) -> LessonWorkerCompactView`,
  `await LessonWorkerService.advance(run_id, request, parent) -> LessonWorkerCompactView`,
  and `LessonWorkerService.review_page(run_id, request, page_position, parent) -> LessonWorkerPageReviewView`;
  `PlannedBundleEvidenceResolver.resolve(plan, bundle, revision_commitments,
  context) -> ResolvedPlannedBundleEvidence`;
  `FlashcardProfileTaskBinding.expectation -> ProfileTaskExpectation` and
  `build(task_id, public_inputs, prepared_scope, context) -> GenerationWorkerTask`;
  `PlannedBundleWorker.start(task, prepared_scope, context) -> WorkerCompactView`
  and `detail(task_id, prepared_scope_fingerprint, context) -> VerifiedFlashcardPageResult`;
  `LessonWorkerStore.create(key, payload) -> bool`,
  `compare_and_set(key, expected, replacement) -> bool`, and
  `load(key) -> bytes`. `start` is async like B1; `review_page`, resolver,
  binding, detail, and store operations are synchronous.
- The resolver returns one `EvidenceEnvelope` for one bundle. Before any child
  claim, reconstruct and validate it as exactly one ordered evidence item per
  planned slot: same source id, revision id, start/end offsets, and locator;
  sufficient status; unique handles; exact ordered read-set fingerprint; no
  missing, extra, merged, split, reordered, overlapping, or drifted item. Reject
  more than 24 items. A source revision that cannot resolve exactly is stale,
  never silently re-retrieved from another revision. Its typed result also
  carries the exact ordered revision commitments observed during resolution;
  they must equal the request's complete bindings. Resolver inputs, result,
  wrapper, checkpoint, lesson/child identities, and stale checks all commit the
  same revision-to-content fingerprints, not only revision ids or chunk hashes.
- Deterministically build the legacy `PreparedFlashcardScope`: all C0A index
  entries remain compact navigation metadata in canonical order; only active
  bundle topics link the exact resolved handles; the evidence envelope contains
  only that bundle. Then call `PreparedPlannedFlashcardScope.prepare(...)` and
  `validate_against_plan(...)`. Do not edit or reinterpret either existing
  scope codec.
- Add `BoundPlannedFlashcardScopeExecutor` named
  `source.prepare_planned_flashcard_scope@1`. It is constructed with one exact
  request and one exact `PreparedPlannedFlashcardScope`, accepts exactly
  the public `query`/`scope` tool arguments bound at construction, and returns
  only the wrapper JSON. `ToolExecutor.invoke` receives no execution context, so
  it must not pretend to re-authorize: the concrete planned-worker adapter checks
  the trusted context/request/authority binding before constructing the executor.
  The executor itself rejects only changed/extra query/scope arguments. Provide
  a narrow helper returning this private `ToolExecutor`; do not register a
  StudyTool or widen `source.prepare_flashcard_scope@1`.
- Define immutable `ProfileTaskExpectation` with its own domain-separated
  fingerprint over the exact profile fingerprint, capability id/version,
  manifest fingerprint, required authority, complete `VersionPins`, definition
  fingerprint, output schema plus fingerprint, and ordered
  `ValidationExpectation` values. The request embeds this complete expectation,
  not a lone opaque profile fingerprint.
- The injected profile task binding receives the coordinator-derived child task
  id, exact public inputs, wrapper, and parent context and returns a strict B1
  `GenerationWorkerTask`. The coordinator verifies task kind
  `flashcard_bundle` and compares every returned task field against
  `ProfileTaskExpectation`: capability/manifest, authority, pins, definition,
  output schema/fingerprint, and ordered validations. It also checks exact public
  payload, profile expectation fingerprint, task id,
  index references committing plan+bundle+wrapper, and evidence references
  equal to the ordered active handles. Changed profile, prompt, skill, playbook,
  validator expectations, output schema, or task bytes is stale/conflict.
- Domain-separate stable identities. The lesson run identity commits request
  fingerprint plus trusted authority fingerprint. Each child task identity
  commits lesson run, plan, profile binding, canonical bundle position/id, and
  wrapper/read-set and revision-content fingerprints. Exact retry produces byte-identical identities;
  two authorities cannot share a coordinator run.
- Persist a repeatable operational state machine before effects:
  `pending -> resolving -> prepared -> child_claimed -> child_terminal`, with a
  terminal lesson status only after every page is terminal. Store the exact
  prepared-wrapper bytes (bounded to 512 KiB per page) before B1 delegation so a
  crash does not repeat successful resolution. A crash after child claim retries
  the same B1 task id; B1 recovery supplies the one durable child run/model
  effect. A crash after B1 completion but before coordinator CAS inspects/reuses
  the B1 terminal receipt and detail. Completed pages never resolve evidence or
  delegate again. CAS losers reload identical state or conflict.
- The canonical coordinator checkpoint, including the total bytes of every
  referenced prepared-wrapper record, is bounded to 8 MiB. Exceeding it fails
  explicitly with `lesson_worker_checkpoint_limit_exceeded`; it is never
  truncated. Keep the independent 512 KiB per-page wrapper bound.
- Permit at most 256 planned pages and fail explicitly with
  `lesson_worker_page_limit_exceeded`; never truncate. A no-work C0A plan
  completes with zero pages and performs no resolution/delegation. Concurrency
  is a global in-flight cap, not a per-call launch count: `advance` first counts
  all persisted non-terminal `child_claimed`/running pages and may claim only
  the remaining capacity. Repeated `advance` calls while children remain running
  cannot exceed the configured cap. Completion order must not
  affect persisted or returned order: pages are always canonical plan order.
  C0A v1 has no separately evidenced overview kind, so do not synthesize an
  overview or duplicate evidence.
- Treat B1 `running` as retryable in-progress; `suspended` is an incompatible
  coordinator result because B2 always supplies a non-null scope; terminal
  failed/cancelled/stale/terminated pages are recorded without exposing detail.
  Do not convert an incomplete or failed lesson to success.
- Define strict B2-owned `VerifiedFlashcardPageResult` with candidate/omission
  counts, output fingerprint, receipt/run commitments, and the verified B1
  detail used by one-page review. The concrete profile adapter added by C1/C2/C3
  must decode the public output through `FlashcardCandidateBatch` and construct
  this result; the coordinator must not import artifact owners or hand-parse raw
  output tuples. Enforce the request ceiling and persist only compact counts/
  fingerprints, child run id, and receipt fingerprint. The compact host view exposes run/plan/profile
  ids, canonical completed/failed/pending positions, candidate and omission
  counts, failure codes, `advance_required` while any page is nonterminal, and
  `in_progress` only while a child is claimed/running—never evidence text,
  candidate bodies, worker scratch output, authority, or provider data. The
  typed review API returns exactly one authorized page by canonical position,
  its planned metadata/wrapper commitments, and B1 verified detail; it does not
  materialize an unbounded whole-lesson payload.
- Exact JSON codecs use reconstruct/freeze/canonical-byte equality. Fingerprints
  are domain-separated and every decoded checkpoint revalidates request, plan,
  page order, child identities, wrapper/receipt commitments, and bounds. Store
  only operational state: no canonical event, artifact acceptance/publication,
  learner state, StudyTool, Anki field, hosted queue, or model-specific type.
- `LessonWorkerRequest.to_public_inputs()` is the sole payload transformation and
  yields exactly `query`, `scope`, `language`, `candidate_ceiling`, and
  `continuation_summary_json`. The last value is `null` or the UTF-8 decoded
  canonical compact JSON bytes of the structured continuation object
  (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, no NaN).
  Binding and returned-task checks require byte-identical transformation; no
  second parser, free-form summary string, preferences, or profile data enters
  the public capability payload.

## Recovery Boundaries

- Crash before resolution CAS: resolution may retry, with no child effect.
- Crash after prepared scope CAS: reuse exact stored wrapper; do not resolve again.
- Crash after child claim/start: retry the byte-identical B1 task and rely on its
  persisted child identity.
- Crash after child terminal but before page CAS: read B1 terminal view/detail,
  verify the same receipt, then persist the same compact page receipt.
- Crash after page CAS: never call resolver or B1 for that page again.

## Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/flashcards/test_lesson_worker_contracts.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/unit/tools/test_planned_flashcard_scope_bridge.py \
  tests/integration/test_lesson_worker_recovery.py \
  tests/architecture/test_lesson_worker_boundaries.py \
  tests/contract/tools/test_public_tool_contract.py
.venv/bin/ruff check \
  src/study_agent/flashcards/lesson_worker_contracts.py \
  src/study_agent/flashcards/lesson_worker_service.py \
  src/study_agent/flashcards/lesson_worker_view.py \
  src/study_agent/ports/lesson_worker.py \
  src/study_agent/tools/planned_flashcard_scope_bridge.py
.venv/bin/mypy --strict \
  src/study_agent/flashcards/lesson_worker_contracts.py \
  src/study_agent/flashcards/lesson_worker_service.py \
  src/study_agent/flashcards/lesson_worker_view.py \
  src/study_agent/ports/lesson_worker.py \
  src/study_agent/tools/planned_flashcard_scope_bridge.py
git diff --check
```

## Report

Report public names, identity/fingerprint domains, exact source-resolution
checks, state transitions and crash recovery evidence, compact/detail separation,
and verification results. Do not edit tests, commit, or delegate.
