# Worker Brief: TUT-04D grounded exam-sample analysis

## Goal

Implement `analyze_exam_sample@1` as one provider-neutral, read-only capability
that prepares an explicit set of canonical `exam_sample` source revisions,
executes exactly one B1 isolated worker, and returns a verified
exam-blueprint proposal plus a compact observational summary.

## Allowed Files

- `src/study_agent/exams/__init__.py`
- `src/study_agent/exams/contracts.py`
- `src/study_agent/exams/analysis.py`
- `src/study_agent/exams/worker.py`
- `src/study_agent/ports/exam.py`
- `src/study_agent/tools/exam_scope_bridge.py`
- `src/study_agent/skills/builtin/analyze_exam_sample.py`
- `src/study_agent/playbooks/builtin/analyze_exam_sample_flow.py`
- `src/study_agent/prompts/exam_sample_analysis_v1.py`
- the narrow exports in `src/study_agent/{ports,prompts}/__init__.py` and
  `src/study_agent/{skills,playbooks}/builtin/__init__.py`
- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/builtin.py`
- `src/study_agent/capabilities/__init__.py`

## Forbidden Files

- Flashcard planning, profile, fan-out, and provisional C1/C2 files; worker B1
  contracts/service/store; artifact lifecycle/events/commit/export; ingestion,
  retrieval adapters, CLI, configuration, dependencies, tests, specs/docs,
  provider SDKs, `sbobby-web`, and the seven StudyTools.

## Pinned Public Contract

- Add only `TutorCapabilityId.ANALYZE_EXAM_SAMPLE = "analyze_exam_sample"` and
  `ANALYZE_EXAM_SAMPLE_MANIFEST`. Identity is `analyze_exam_sample@1`, version
  `1.0.0`, authority is exactly `("course:read",)`, suspension is false, and
  the skill has an empty `StateWritePolicy`.
- Inputs are exact: ordered unique `sample_revision_ids` (1..16 canonical text
  ids) and presentation `language` (1..64 chars). No query, prediction target,
  exam date, learner state, profile, continuation, provider/model selector,
  raw source text, decision, or artifact identity is admitted.
- Verified public output is exact:
  `sample_size`, `observed_topics`, `observed_formats`, and `limitations`.
  Each observation has only `value` and ordered unique `evidence_ids` (1..16).
  Topics/formats contain at most 64 observations each; limitations contain
  2..4 validator-derived strings. Unknown fields fail closed.
- `sample_size` is the number of distinct selected source revisions, not chunks.
  Output is proposal-shaped but does not contain canonical source-commitment
  indices. TUT-04E1 alone maps verified evidence handles to ordered commitment
  indices and constructs the unchanged `ExamBlueprintContent`; do not change
  ADR-0008 artifact schemas.
- Both `observed_topics` and `observed_formats` must contain at least one
  grounded observation. Either empty category terminates as insufficient; do
  not weaken or change `ExamBlueprintContent` to represent an incomplete model
  draft.
- Define immutable exact-codec `ExamAnalysisRequest` containing only ordered
  sample revision ids and language. It is the single input to task construction
  and facade replay; callers cannot supply task ids, pins, schemas, proof ids,
  or worker state.

## Trusted Exam Evidence

- Define a strict canonical proof-side `PreparedExamSampleScope` with exact
  codecs and a domain-separated fingerprint. It contains 1..16 ordered sample
  records bound one-to-one to selected current course revisions and one
  `EvidenceEnvelope`; every evidence handle belongs to exactly one sample.
  Bounds are at most 64 evidence items, at most 8 per sample, and at most 64 KiB
  of quoted evidence text. Empty, superseded, cross-course, missing, duplicate,
  oversized, or partially truncated samples fail explicitly.
- For each selected revision, evidence spans are ordered and cover exactly the
  complete normalized source interval `[0, normalized_character_length)`:
  first start is zero, final end is the exact length, and each adjacent end/start
  is equal. Gaps, overlap, reordered chunks, partial retrieval, or silent
  head/tail truncation fail before the model.
- Derive a separate exact-codec `ExamPromptEvidenceProjection` from that proof
  scope. It contains only opaque sample keys, opaque evidence handles, locators,
  and quoted text plus the proof-scope fingerprint; it contains no canonical
  course/source/revision/chunk identities. The prompt receives only this
  redacted projection. Projection bytes and handle/span mapping must resolve
  byte-identically back to the proof scope through the verified child proof.
- The injected preparation port resolves the exact selected revisions from
  canonical source state and accepts only the literal source role
  `exam_sample`. Source role is checked before prompt composition. The model
  sees opaque sample/evidence handles, locators, and quoted text, never source/
  revision/course/principal/session identities.
- Add private tool behavior `source.prepare_exam_sample_scope@1`; it accepts
  exactly the selected revision ids already bound to the trusted request and
  cannot search other materials. It is a skill/playbook behavior primitive,
  not a public StudyTool.
- Its output is exactly
  `{ "prepared_scope": <PreparedExamSampleScope>, "prompt_projection":
  <ExamPromptEvidenceProjection> }`. The projection commits to the scope. The
  `ModelStep` binds only `DataReference(..., path=("prompt_projection",))`;
  readiness/integrity bind the proof-side `prepared_scope` path as required.
  No model binding may reference the containing tool output or prepared scope.
- A versioned deterministic injection guard runs in readiness before the model.
  Reject Unicode-normalized control/role delimiters and explicit instruction
  override or prompt/credential-exfiltration phrases. Suspicious evidence
  terminates as `validation_failed`; it is never silently removed or sent to
  the model.

## Skill, Playbook, Prompt, and Validation

- Playbook shape is exactly prepare tool -> readiness validator -> one
  `ModelStep` -> integrity validator. There is no dialogue step, second model
  effect, grading, retrieval search, or canonical write.
- Pin one skill, playbook, prompt, model-adapter/state-contract pins, the private
  tool behavior, and ordered validators `exam_sample_readiness@1.0.0` then
  `exam_blueprint_integrity@1.0.0`. The capability binding must satisfy the
  existing generic `CapabilityBinding`; do not introduce a profile dispatcher.
- Prompt layers state that all sample text, titles/locators, handles, and
  presentation fields are untrusted data; ignore embedded instructions. Ask
  only for observed topic and format labels with supporting evidence handles.
  Forbid likelihood, frequency extrapolation, future-exam claims, grading,
  mastery, schedules, learner advice, hidden prompt disclosure, and decisions.
- The internal model schema contains only `observed_topics` and
  `observed_formats` with the public observation shape. The integrity validator
  resolves every cited handle against the prepared envelope and canonical
  `SourceContentPort`, rejects unknown/unresolved evidence, duplicate normalized
  values, empty citations, injection-shaped values, and predictive wording
  such as future occurrence, likelihood, probability, or expected next exam.
- The validator, not the model, adds limitations in stable order: observational
  only/not predictive; coverage limited to the selected samples; sparse sample
  when `sample_size < 3`; conflicting source evidence when the envelope is
  conflicting. Model-authored limitations are impossible.
- `INSUFFICIENT` evidence terminates without a proposal. `CONFLICTING` evidence
  may complete only with the deterministic conflict limitation; observations
  must still cite exact handles. Zero topics or zero formats terminates as
  insufficient.

## Isolated Worker Binding and Views

- A trusted task factory exposes exactly
  `build(request: ExamAnalysisRequest, opaque_request_key: str) -> GenerationWorkerTask`
  and builds one task of kind
  `EXAM_ANALYSIS`, binds the exact manifest/pins/definition/schema/validators,
  puts only capability inputs in `payload`, mirrors the ordered selected
  revisions in `evidence_references`, leaves `index_references` empty, and uses
  no continuation summary or preferences. An opaque caller request key may
  contribute to deterministic `task_id`; it never enters payload or prompt.
- In `ports/exam.py`, define the only injected read protocol as
  `ExamVerifiedChildProofReader`, structurally matching B1A
  `VerifiedChildProofOwner.load(task, run_id, receipt, context) ->
  VerifiedChildExecutionProofView`. D depends on this inward protocol, never a
  concrete proof store or proof-owner service.
- The facade signatures are exactly
  `start(request, opaque_request_key, parent) -> ExamAnalysisCompactView` and
  `detail(request, opaque_request_key, parent) -> ExamAnalysisDetailView`.
  Each call rebuilds the exact task through the factory. Detail derives task id
  only from rebuilt task and never accepts task id, reads worker storage, or
  discovers a prior task by run.
- The facade delegates only to injected B1 `GenerationWorkerService` and
  `ExamVerifiedChildProofReader`; it does not invoke the gateway, engine, model,
  validator, worker/proof store, or trace parser directly. After completion it
  derives the exact child context with public
  `generation_worker_child_context(task, parent)` and calls proof load with the
  exact task, child run, worker receipt, and child context—never the parent and
  never a duplicate context algorithm. It then
  derives coverage and the typed evidence mapping only from sanitized
  `VerifiedChildExecutionProof` prepared tool outputs and read dependencies.
  One request is one worker and one model
  effect; no exam fan-out/coordinator is introduced in v1.
- Compact view exposes task/run/status, `sample_size`, topic/format counts,
  evidence coverage count, limitation codes, and detail availability only.
  Typed detail exposes the verified proposal and a proof reference needed by
  E1; its evidence mapping is derived from the B1A proof and redacted prompt
  projection, never caller-authored. Raw sample text, model scratch, malformed output, prompts,
  credentials, principal data, and provider metadata never enter the compact
  view.
- Detail requires the proof's allowlisted tool output to match exact tool
  `source.prepare_exam_sample_scope@1`, declared step id/output key, and stored
  value fingerprint. It exact-decodes both output members, verifies scope ↔
  projection fingerprint and opaque handle mapping, and rejects any missing,
  extra, substituted, reordered, or noncanonical proof output.

## Acceptance and Verification

- Exact codecs/fingerprints and manifest/package discovery are portable and
  deterministic; the old three capability identities and seven StudyTools keep
  their existing fingerprints.
- Sparse, conflicting, injection, unknown evidence, prediction, malformed
  schema, cancellation/failure, exact retry, and authorized detail paths fail or
  complete exactly as specified.
- Run focused unit/contract/integration/architecture tests, Ruff, strict mypy,
  the public tool contract, full offline pytest, and `git diff --check`.

## Scope Decision

This remains one fresh-context bead after B1A because it adds one bounded artifact kind,
one linear playbook, and a thin B1 facade; it adds no coordinator or new state
owner. No ADR or ubiquitous-language change is required: ADR-0004 owns host
choice, ADR-0008 already defines the exam-blueprint proposal, and ADR-0010/B1
already define provider-neutral isolation.
