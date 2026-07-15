# Worker Brief: TUT-04C0 production

## Goal

Implement one public `propose_flashcards@1` contract, a strict transient
candidate batch, and trusted out-of-band dispatch to exactly two closed
pedagogical profile bindings without weakening the ordinary capability gateway.

## Allowed Files

- `src/study_agent/artifacts/candidates.py`
- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/bindings.py`
- `src/study_agent/capabilities/dispatch.py`
- `src/study_agent/capabilities/gateway.py`
- `src/study_agent/capabilities/builtin.py`
- `src/study_agent/capabilities/__init__.py`
- `src/study_agent/skills/builtin/propose_flashcards.py`
- `src/study_agent/skills/builtin/__init__.py`

`src/study_agent/artifacts/__init__.py` is reserved for orchestrator integration
because TUT-04B owns it concurrently; import candidate contracts from their
module in this pass.

## Forbidden Files

- All domain, artifact lifecycle/event/projection/service/view/port files,
  prompts/playbooks/profile implementations, adapters, tools, composition
  roots, CLI/export, tests, docs/specs, dependencies, configuration, and
  `sbobby-web`.

## Required Context

- ADR-0008/0009, TUT-04C0, TUT-03 capability gateway contracts, TUT-04A profile
  receipts, and existing optional-dialogue checkpoint behavior.
- C1/C2 will supply real profile-specific prompts/playbooks/validators. C0 must
  not invent placeholder production generation behavior.

## Public Contract

- Add exactly one discovered identity: `propose_flashcards@1`. Internal profile
  skill/playbook identities are not `TutorCapabilityId` values and never appear
  in discovery.
- Public input is an exact task envelope: trimmed `query` (1..4000 chars),
  nullable trimmed `scope` (1..1000 when present), trimmed `language` (1..64),
  `candidate_ceiling` integer 1..24, and nullable
  `continuation_summary_json`. When present, the summary is canonical compact
  JSON text for one object, at most 16 KiB UTF-8; dispatcher validation enforces
  bounds not expressible in the repository JSON-schema subset. Profile/provider/
  model/Anki/lifecycle/canonical identity fields are absent.
- Capability output is the strict verified transient candidate batch used by
  C1/C2. It is not a canonical artifact batch and cannot write state.
- Candidate batch is exact `{candidates, omissions}` with 0..24 candidates and
  0..24 unique omission records. An omission is exactly `{reason,
  evidence_ids}`: trimmed reason (1..1000 chars) and 0..16 unique opaque
  evidence IDs.
- A candidate has exactly: `candidate_key`, nullable `parent_candidate_key`,
  `retrieval_form`, `prompt`, `answer_blocks`, `pedagogical_role`, nullable
  `morphology_family`, nullable `cognitive_function`, `rationale`,
  `evidence_ids`, and `media_evidence_ids`. Keys are trimmed opaque temporary
  IDs of 1..128 chars; prompt/rationale are 1..4000; answer blocks are 1..8
  exact `{label,text,key_points}` records with 1..200 labels, 1..4000 text and
  0..12 unique key points; evidence IDs are 1..16 unique opaque strings of
  1..256; media evidence IDs are 0..8 unique opaque strings of 1..256.
- Retrieval form is the TUT-04A closed vocabulary. Role is the disjoint union
  `overview|section|detail|macro_reconstruction|atomic_discrimination`, which
  discriminates profile shape without a profile field. Family is nullable
  `components|topology|relations|course|profiles|landmarks`; cognitive function
  is nullable `reconstruct|localize|relate|discriminate`. C0 validates vocabulary
  and shape; C1 requires hybrid roles plus null morphology fields, while C2
  requires morphology roles plus non-null family/function.
- Parent key must name a lower same-batch candidate. Evidence/media IDs are only
  opaque handles emitted from trusted retrieval/media steps; they contain no
  source/blob/digest/verifier receipt. C1/C2 validators must resolve every handle
  against trusted step outputs before a verified run may be recovered.
  It forbids canonical IDs, status/decision, profile receipt/discriminator,
  provider/model/credential, Anki/deck/tag/template/HTML/filename, and
  model-authored verifier/blob receipts.

## Specialized Binding and Dispatch

- Do not add generic hidden/trusted input support to `CapabilityBinding`.
  Existing bindings, manifest bytes, run identities, and public gateway methods
  remain compatible.
- Add a closed `ProfiledCapabilityBinding` for this one public manifest. It
  binds one exact catalog profile to profile-specific skill/playbook/prompt/
  validator pins, uses empty state-write policy, and permits exactly one
  reserved checkpoint input key: `profile_selection_receipt`.
- Public skill input/output schemas equal the manifest. The internal playbook
  inputs equal public inputs plus the receipt key. The receipt key must be
  disjoint from public fields and no tool/model/dialogue/validator DataBinding
  may read it.
- Dispatcher construction requires exactly one hybrid and one morphology
  binding, with no duplicates, unknown versions, registration, or placeholder
  fallback. Their internal skill identities, playbook identities, and playbook
  definition fingerprints must be pairwise distinct so existing-run ownership
  is unambiguous.
- `start(inputs, context, selection=None)` validates public input, builds the
  exact hybrid default receipt only when omitted (`mode=default`,
  `selector_kind=host`, empty basis, and `selector_authority` equal to the
  executing trusted HUMAN/SERVICE context principal kind), validates it against
  the closed catalog, selects the binding, and persists canonical receipt JSON
  inside the existing run/checkpoint inputs.
- `resume(continuation, response, context)` accepts no replacement receipt. It
  validates/decodes the persisted receipt and chooses the same binding.
- Reuse the gateway execution owner through package-private bound start/resume
  helpers. Do not duplicate recovery, authorization, run-store, continuation,
  output validation, or error mapping logic and do not add another state owner.
- On every completed start/resume outcome, after ordinary manifest validation
  and before returning `CompletedCapabilityOutcome`, decode output through the
  strict shared `FlashcardCandidateBatch` codec and return its canonical JSON.
  Codec failure maps to the existing safe FAILED outcome and never yields a
  recoverable verified proposal batch.
- Keep run identity based on public capability/manifest, authority, and retry
  identity. The persisted receipt and internal pins make same-key changed
  profile/basis/mode/pins conflict rather than create a second run.
- Selection is per batch, never a learner trait. Course title and model output
  cannot influence selection. MODEL remains unauthorized. Do not require the
  authority of an explicitly supplied receipt to equal the executing trusted
  host authority; only an omitted/default receipt uses the executor kind above.

## Discovery and Existing-Run Recovery

- TUT-04C0 does not register duplicate bindings in `StudyCapabilityGateway`.
  The ordinary gateway and its two-entry explain/assess discovery remain
  unchanged. `FlashcardCapabilityDispatcher.discover()` returns exactly the one
  public flashcard manifest and executes through package-private gateway bound
  helpers. A future composition facade may merge discovery surfaces after
  C1/C2; C0 does not invent it.
- Before starting or recovering, compute the public run ID and inspect it across
  exactly the two closed playbook definitions without executing effects. If one
  definition owns the checkpoint, decode its persisted canonical receipt first,
  then compare requested selection and internal pins. A changed profile/basis/
  mode/pins returns `CONFLICT`, not `INCOMPATIBLE_RUNTIME`, and performs no
  model/tool call. No matching checkpoint permits execution with the newly
  selected binding; corrupt or multiply matching state fails incompatible.
- Resume similarly locates the owner from the persisted continuation/run across
  the two closed definitions, then validates receipt, definition, pins,
  authority, dependencies, and checkpoint generation before any effect.

## C0/C1/C2 Split

- C0 defines only shared public schemas, manifest, candidate codecs, dispatcher,
  and profiled-binding contracts. It creates no placeholder `SkillPackage`,
  prompt, playbook, or validator.
- C1/C2 each provide a real internal non-`TutorCapabilityId` SkillPackage and
  playbook that reuse the shared public schemas. Those packages are the skills
  held by `ProfiledCapabilityBinding`.
- Until TUT-04B releases `artifacts/__init__.py`, production and tests import
  candidates directly from `study_agent.artifacts.candidates`; package re-export
  is an orchestrator integration step.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing capability/gateway/continuation/portability tests.
- `git diff --check`

## Report

Report public names, exact schemas, gateway compatibility strategy, commands
and results, and any ambiguity. Do not edit tests, commit, or delegate.
