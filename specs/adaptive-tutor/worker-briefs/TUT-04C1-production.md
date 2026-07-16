# Worker Brief: TUT-04C1 hybrid macro-detail profile

## Goal

Implement the closed `hybrid-macro-detail@1` profile for one exact C0A/B2
lesson bundle. The profile preserves the hierarchy-aware method from
`generate-hybrid-anki-flashcards`, but returns one verified transient
`FlashcardCandidateBatch`; it never emits Anki fields or canonical artifacts.

## Allowed Files

- replace the provisional files:
  - `src/study_agent/prompts/hybrid_flashcards_v1.py`
  - `src/study_agent/skills/builtin/hybrid_flashcards.py`
  - `src/study_agent/playbooks/builtin/hybrid_flashcards_flow.py`
  - `src/study_agent/capabilities/hybrid_flashcards.py`
- consume the completed TUT-04C0B1B `ProfiledWorkerExecutionDescriptor`; do not
  amend the shared worker adapter from this profile bead.

## Forbidden Files

- All other production files, package exports, C0A/B1/B1A/B2 contracts,
  dispatcher, public manifest/schemas, artifact/event/state owners, adapters,
  CLI, configuration, dependencies, tests, docs/specs, and `sbobby-web`.
- No registry keyed by task/wrapper, global mutable request state, provider SDK,
  direct model call, second worker system, new public capability, or StudyTool.

## Exact Identities And B2 Adapter

- Pin internal skill `propose_flashcards_hybrid@1`, playbook
  `propose_flashcards_hybrid_flow@1`, prompt `hybrid_flashcards.v1`, validators
  `hybrid_flashcards_readiness@1` and `hybrid_flashcards_integrity@1`, and the
  private tool `source.prepare_planned_flashcard_scope@1` at `1.0.0`.
- Keep the existing public `propose_flashcards@1` manifest, public input/output
  schemas, `hybrid-macro-detail@1` receipt, empty state writes, and structured
  output fallback through the integrity validator. Define a stricter private
  model schema; ModelStep and fallback parse that schema, never the public one.
- Provide one concrete request-scoped composition implementing both B2 ports:
  `FlashcardProfileTaskBinding` and `PlannedBundleWorker`. It is constructed with
  the exact `LessonWorkerRequest`, B1 store, gateway/proof owner, trusted model/
  state pins, source-content port, and other existing engine dependencies.
  `expectation` is derived from the exact binding. `build(...)` returns the exact
  B1 `GenerationWorkerTask` required by B2, including public payload,
  `flashcard_bundle` kind, empty preferences, canonical continuation object,
  B2 index/evidence references, exact output schema, definition/pins, and ordered
  readiness/integrity expectations.
- `start(task, prepared_scope, context)` reconstructs and validates the exact
  request-bound `PreparedPlannedFlashcardScope`, builds
  `BoundPlannedFlashcardScopeExecutor(request, prepared_scope)`, then delegates
  exactly once through `GenerationWorkerService` and
  `GatewayIsolatedCapabilityRunAdapter`. It must not call dispatcher, gateway,
  engine, model, validator, or tool in parallel with or outside that chain.
  `detail(...)` authorizes through B1, decodes only
  `FlashcardCandidateBatch.from_json`, verifies the wrapper fingerprint expected
  by the task, and returns B2 `VerifiedFlashcardPageResult` with exact counts,
  output fingerprint, and unchanged B1 detail.
- A profiled B1 run has two input views: B1 task/input/receipt commitments stay
  over `task.capability_inputs()` (the five public fields), while the trusted
  gateway execution input adds exactly `profile_selection_receipt`. The minimal
  B1B descriptor reconstructs the exact persisted selection receipt from the
  request; task/model/prompt data and child context cannot author it.
  Preserve B1A proof creation, public output, fingerprints, resume behavior, and
  all non-profiled bindings byte-for-byte. Do not add the receipt to
  `GenerationWorkerTask`, `LessonWorkerRequest.to_public_inputs()`, or model/tool
  bindings.

## Playbook And Prompt Contract

- Inputs are exactly the five public manifest fields plus the reserved profile
  receipt required by `ProfiledCapabilityBinding`. Steps are: request-bound
  planned-scope ToolStep; readiness ValidateStep; the existing nullable-scope
  DialogueStep with exact `{provided: boolean, text: string}` response/default;
  one ModelStep; one integrity ValidateStep returning `candidate_batch`.
  B2 supplies non-null scope, so normal lesson workers never suspend.
- The model receives only: presentation language; untrusted query,
  clarification and canonical continuation summary; the compact whole-lesson
  index; exact active-bundle classifications; and exact active evidence. It
  receives no tutor history, sibling draft, inactive raw text, credentials,
  principal data, provider choice, or canonical authority. Shape examples are
  examples only, never facts.
- The private draft contains exactly:
  - one ordered `topic_plan` record for each active topic, with exact topic key,
    disposition `generate|omit_scaffolding|omit`, ordered unique candidate keys,
    and nullable omission reason;
  - public-shaped `candidates` and `omissions` arrays;
  - one `detail_bases` record (`fragile|not_recoverable`) for every and only
    detail candidate.
- Instruct the model to read the whole compact index for lesson scale, then act
  only on the active eligible bundle. For every bundle, emit all section
  frameworks before any earned detail. C0A v1 has no separately evidenced
  overview bundle, so C1 must not synthesize overview cards; retain overview
  support only as a fail-closed future bundle-kind branch if that enum is later
  versioned upstream.
- Frameworks test one circumscribed reconstruction, comparison, sequence, or
  mechanism. Details test only fragile facts not recoverable from their linked
  framework: numbers, thresholds, markers, named exceptions, exact locations,
  arrest points, bottlenecks, or high-confusion pairs. Forbid reverse/restatement
  cards, paragraph-by-paragraph conversion, low-yield trivia, duplicated
  prompts/answers, mixed retrieval jobs, unsupported facts, HTML, tags, deck/
  scheduler fields, model/provider choices, canonical IDs, and artifact
  decisions.
- Every budget is a ceiling, never a quota. The only count rule is the request
  ceiling and hard per-page bound 24. Do not encode a 16–22 default, a 24-card
  lesson target, minimum cards per topic/bundle/lesson, or proportional cards by
  source length. Zero-card bundles are valid with explicit grounded omissions.

## Integrity, Grounding, And Quality Boundary

- Decode `PreparedPlannedFlashcardScope`, not legacy scope alone. Require its
  exact wrapper/plan/bundle/kind/topic-order/classification commitments and
  sufficient active evidence. C0A currently prepares only planner-eligible
  active topics; the draft may omit them but cannot name inactive,
  context-only, or excluded topics.
- Require `topic_plan` to cover active topics exactly once in canonical order.
  Every candidate is assigned to one or more generated topics; every omission
  disposition owns no candidates and maps bijectively to one public omission.
  No payload survives when planning fields are stripped.
- Topic pages contain only direct-recall `section` then `detail` candidates,
  null morphology fields, and no media. Every detail parents an earlier
  same-page section. A section may cover several active topics; repeated topic
  assignment is not duplicate output. Require one detail basis for every and
  only detail.
- Candidate evidence must be a non-empty subset of the assigned active topics'
  handles. Resolve every referenced handle through `SourceContentPort` and
  require citation and text equality with the prepared envelope. Evidence in
  index metadata is navigation, not factual support.
- Enforce exact candidate keys/payloads, normalized prompts, normalized answer
  text/key points, role/parent order, ceiling, and conservative duplicate or
  containment-equivalent rejection. Fail closed on unknown/extra fields and
  malformed fallback output.
- Enforce only mechanically decidable properties. “Good framework,” actual
  fragility, non-recoverability, semantic overlap, 2–4 labeled macro lines,
  visible-character targets, and pedagogical yield remain prompt/eval quality
  properties unless a deterministic validator can measure them without source
  interpretation. C3 evals calibrate those judgments; C1 must not claim proof.
- Return only `FlashcardCandidateBatch.to_json()`. Never create, accept, publish,
  tag, schedule, or push an artifact.

## Replacement Strategy

The four current untracked C1 files are provisional evidence. Replace them in
place rather than extending them. Salvage only provider-neutral schema helpers,
strict JSON decoding, normalization utilities, and candidate grounding checks
after reconciling names and wrapper usage. Delete/rewrite the legacy-scope tool
pin, `content|scaffolding|skip` model vocabulary, `local_ceiling`, 16–22 prompt,
whole-index topic-plan requirement, synthesized overview behavior, and any
missing B2 adapter. No compatibility promise applies because these files are
untracked and unshipped.

## Verification

- Focused C1 tests from the paired brief.
- Existing B1A adapter/proof, B2 coordinator/tool, profile binding/dispatcher,
  playbook/skill architecture, and public tool-contract suites.
- Ruff and strict mypy for every allowed production file; `git diff --check`.

## Report

Report the exact profile/task/worker composition, public versus execution input
split, enforced versus prompt/eval pedagogy, retained provisional code, and all
commands. Do not edit tests, docs/specs, commit, or delegate.
