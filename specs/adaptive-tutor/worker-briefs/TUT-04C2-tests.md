# Worker Brief: TUT-04C2 morphology profile tests

## Goal

Independently pin the final morphology-first prompt, exact C0A/B1/B1A/B2
composition, exporter-neutral profile adapter, strict macro/atomic structure,
grounding, and verified-media path. Tests must distinguish enforceable contracts
from medical or pedagogical judgments that deterministic code cannot prove.

## Allowed Files

- `tests/unit/prompts/test_morphology_flashcards_prompt.py`
- `tests/unit/skills/test_morphology_flashcard_skill.py`
- `tests/unit/playbooks/test_morphology_flashcards_flow.py`
- `tests/unit/capabilities/test_morphology_flashcards.py`
- `tests/integration/test_morphology_lesson_worker.py`
- `tests/architecture/test_morphology_flashcard_boundaries.py`

## Forbidden Files

- Production, shared fixtures, existing tests, docs/specs, dependencies,
  provider SDKs, Anki integration, and `sbobby-web`.

## Required Coverage

### Prompt and profile translation

- Pin trusted host selection of `morphology-first-anatomy@1`, complete-index /
  active-evidence separation, fresh-worker isolation, reconstruction before
  discriminations, <=3 earned atomics, zero-card/zero-atomic validity, no numeric
  target, source gaps as omissions, and untrusted-data/prompt-injection policy.
- Pin the exact mapping to closed families `components|topology|relations|course|
  profiles|landmarks`, functions `reconstruct|localize|relate|discriminate`, and
  the closed atomic earning-basis vocabulary. Object, topology, relation, course,
  muscle-profile, landmark, and closed-enumeration shape examples are examples
  only and contain no factual authority.
- Assert explicit exporter-neutral exclusions: no HTML/Markdown, Anki Basic or
  Cloze syntax, deletion indices, deck, tags, template, scheduler, filename,
  provider/model choice, canonical ids, or artifact decisions. Pin that
  `contextual_gap` is only a semantic atomic relation/course form, never
  `{{cN::...}}` product syntax.

### Skill, playbook, and task binding

- Pin exact skill/playbook/prompt/validator identities, public input and output
  schemas, private draft schema, empty state-write policy, private planned-scope
  tool behavior, structured-output fallback, and final public candidate output.
- Pin exactly five steps in order: planned-scope tool, readiness, one
  nullable-scope-gated dialogue, one model, integrity. Null scope suspends with
  exact `{provided, text}` output; coordinated non-null scope takes the canonical
  default without suspension. Both paths retain exactly one model effect after
  any required resume.
- Build a real final `PreparedPlannedFlashcardScope`; assert the tool output and
  validator consume its exact plan/bundle/active-topic/classification
  commitments and preserve legacy `PreparedFlashcardScope` bytes.
- The concrete task binding must equal the final B2 `ProfileTaskExpectation` and
  `GenerationWorkerTask` field for field: exact public payload from
  `to_public_inputs`, empty preferences, exact language/continuation, full pins,
  manifest/definition/schema/ordered validations, B2 index references, and
  active evidence handles. Changed prompt, profile, wrapper, plan, task id,
  revision/read-set, authority, or validator pin fails closed.

### Private draft and pedagogy

- Passing fixtures cover one object macro with zero atomics, one macro plus each
  earned atomic basis, multi-topic object reconstruction, topology, relation,
  course, muscle profile, landmark discrimination, compact contextual gap,
  grounded all-topic omission, closed enumeration, and one verified-media
  candidate.
- Fail missing/reordered/duplicate object plans, inactive or non-eligible topic
  elevation, overlapping/uncovered topics, unknown candidates, orphan atomics,
  atomic before macro, >3 atomics, wrong parent, multiple macros per plan,
  duplicate candidate assignment, extra/unreferenced omissions, and count above
  the requested or hard page ceiling.
- Fail incompatible family/function/retrieval combinations, macro contextual
  gaps, macro function other than reconstruct, absent/generic atomic earning
  basis, dimension/answer-label mismatch, >5 dimensions, nonparallel labels,
  duplicate/containment-equivalent prompt-answer payloads, and model-authored
  product/provenance fields.
- Confirm zero atomics and zero candidates are accepted. Do not assert that a
  validator can infer all spatial inversions, medical correctness, semantic
  redundancy, or whether an atomic is genuinely high value. A hostile spatial
  statement fails only when its cited text conflicts with exact canonical
  evidence.

### Grounding and media

- Pass exact active source resolution. Fail missing, inactive, unlinked,
  duplicate, reordered, or drifted evidence; claims based only on global-index
  headings; external facts; and unsupported source-gap repair.
- Pass at most one opaque verified media handle. Fail unknown/mismatched handle,
  inactive or plan-unlinked evidence, citation drift, >1 media item, path or
  filename, model-authored blob/digest/verifier fields, and media-only cards.
  Foundation tests remain the owner of blob/digest/verifier codec invariants;
  C2 tests verify only the trusted resolver boundary.

### Isolation and B1A proof

- Recording model assertions prove the request contains only the pinned prompt,
  public query/language/ceiling/continuation, compact global index, active
  wrapper/evidence, and private schema. Tutor history, siblings, inactive raw
  spans, credentials, principal fields, provider selection, and proof data are
  absent.
- A real/recording B1 wrapper proves one complete child capability run and one
  playbook-owned model effect. No C2 adapter model call is permitted.
- On completion, require exact `FlashcardCandidateBatch` decoding and an exact
  B1A proof load with task, child run, B1 receipt, and parent. Assert proof binds
  the planned-scope tool output/wrapper, prompt, model receipt, ordered
  fallback/explicit validations, public output, and fingerprints. Changed or
  missing proof, task, authority, wrapper, tool output, output, prompt, model,
  validator order/disposition, or receipt fails before
  `VerifiedFlashcardPageResult` construction. `response_id=None` passes and is
  preserved.
- The verified page count/fingerprint/detail exactly match the proof-backed B1
  output. Compact tutor views contain no proof, evidence text, model metadata,
  provider data, or authority.

### Architecture

- C2 imports inward domain/ports and generic B1/B1A/B2 contracts only; it adds no
  provider SDK, event/state/artifact write, StudyTool, product/Anki dependency,
  public manifest change, legacy preparation change, or import cycle.
- Clean-process imports cover morphology module first and capability/worker
  packages first.

## Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/prompts/test_morphology_flashcards_prompt.py \
  tests/unit/skills/test_morphology_flashcard_skill.py \
  tests/unit/playbooks/test_morphology_flashcards_flow.py \
  tests/unit/capabilities/test_morphology_flashcards.py \
  tests/integration/test_morphology_lesson_worker.py \
  tests/architecture/test_morphology_flashcard_boundaries.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/workers/test_verified_child_proof.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/integration/test_gateway_worker_proof_recovery.py \
  tests/architecture/test_gateway_worker_adapter_boundaries.py \
  tests/architecture/test_lesson_worker_boundaries.py \
  tests/contract/tools/test_public_tool_contract.py
.venv/bin/ruff check \
  tests/unit/prompts/test_morphology_flashcards_prompt.py \
  tests/unit/skills/test_morphology_flashcard_skill.py \
  tests/unit/playbooks/test_morphology_flashcards_flow.py \
  tests/unit/capabilities/test_morphology_flashcards.py \
  tests/integration/test_morphology_lesson_worker.py \
  tests/architecture/test_morphology_flashcard_boundaries.py
.venv/bin/mypy --strict \
  src/study_agent/prompts/morphology_flashcards_v1.py \
  src/study_agent/skills/builtin/morphology_flashcards.py \
  src/study_agent/playbooks/builtin/morphology_flashcards_flow.py \
  src/study_agent/capabilities/morphology_flashcards.py
git diff --check
```

## Report

Report production mismatches only, grouped as contract, pedagogy, grounding,
proof, or architecture. Do not edit production, commit, delegate, or broaden
the allowed files.
