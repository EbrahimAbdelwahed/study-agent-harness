# Worker Brief: TUT-04C0 tests

## Goal

Independently pin the single public flashcard capability, transient candidate
contract, and trusted profile dispatch/retry/resume boundary.

## Allowed Files

- `tests/unit/artifacts/test_flashcard_candidate_contracts.py`
- `tests/unit/capabilities/test_flashcard_dispatch.py`
- `tests/architecture/test_flashcard_capability_boundaries.py`
- `tests/unit/capabilities/test_capability_contracts.py`
- `tests/architecture/test_artifact_contract_boundaries.py`

## Forbidden Files

- Production, docs/specs, other tests, lifecycle/events/projection/service,
  prompts/playbooks/adapters/tools, CLI/export, dependencies, configuration,
  and `sbobby-web`.

## Acceptance Criteria

- Discovery contains one `propose_flashcards@1`; internal profile implementation
  IDs are absent. Existing explain/assess manifest bytes remain unchanged and
  exactly seven public StudyTools remain.
- Manifest input/output has no selection/provider/model/credential/Anki/state
  field and state-write policy is empty.
- Candidate codec pins the exact production field/cardinality/text bounds,
  round-trips canonically, accepts 0 and 24, rejects 25,
  duplicate keys, missing/self/forward parent, canonical IDs, lifecycle/profile
  fields, provider/model/API keys, Anki/deck/tag/template/HTML/media filenames,
  and model-authored blob/verifier receipts.
- Profiled binding requires exactly the public manifest plus closed profile,
  schema/pin/suspension agreement and reserved receipt input. Missing/duplicate/
  unknown profiles, public-key collision, any step binding from receipt, and
  non-empty writes fail.
- Hybrid and morphology internal skill/playbook identities and definition
  fingerprints must be distinct; otherwise dispatcher construction fails.
- Omitted receipt selects hybrid; explicit hybrid and explicit/trusted
  morphology route correctly; invalid default/version/basis/MODEL selection
  fails. Course-title/model output cannot drive routing.
- Omitted selection persists one canonical default receipt whose authority is
  exactly the executing trusted HUMAN/SERVICE context kind.
- Exact retry reuses one run. Same key with changed profile, basis, mode, or
  internal pins conflicts before another model/tool execution. Existing-run
  lookup probes exactly the two closed definitions, decodes the stored receipt,
  and reports changed selection as conflict rather than incompatible runtime.
- A completed output that passes JSON Schema but violates codec-only rules
  (duplicate evidence IDs, forward parent, oversized text, or conditional
  role/nullability) becomes FAILED before a completed outcome or recoverable
  verified batch is exposed.
- Continuation persists exact canonical receipt; resume has no selection
  parameter and selects only from checkpoint input. Tampered receipt, pins,
  definition, authority, or checkpoint generation conflicts. Process-loss
  recovery chooses the same binding without another state owner.
- Existing gateway public API, explain/assess behavior, run IDs, and
  continuation compatibility remain unchanged.
- Dispatcher discovery alone returns the single flashcard manifest; ordinary
  gateway discovery remains the two existing explain/assess manifests. No
  duplicate public-id registration or premature unified facade is introduced.
- Import candidate contracts directly from `study_agent.artifacts.candidates`;
  do not require or edit the package export while TUT-04B owns it.

## Verification

- New focused tests plus existing capability/gateway suites, Ruff, strict mypy,
  and `git diff --check`.

## Report

Report production mismatches as concrete findings. Do not edit production,
commit, or delegate.
