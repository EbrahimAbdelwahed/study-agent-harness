# Worker Brief: TUT-04C0B1B profiled worker execution

## Goal

Implement the minimum shared contract that lets B1/B1A execute a closed
`ProfiledCapabilityBinding` without widening the five-field public flashcard
payload or losing exact profile-selection, retry, and proof commitments.

## Allowed Files

- `src/study_agent/flashcards/lesson_worker_contracts.py`
- `src/study_agent/capabilities/bindings.py`
- `src/study_agent/capabilities/dispatch.py`
- `src/study_agent/capabilities/gateway.py`
- `src/study_agent/capabilities/worker_adapter.py`
- `src/study_agent/workers/contracts.py`
- `src/study_agent/workers/service.py`
- `src/study_agent/workers/proof.py`

## Forbidden Files

- All other production files, tests, docs/specs, dependencies, configuration,
  C1/C2 profile/prompt/skill/playbook modules, artifact/event/state owners,
  provider adapters/SDKs, CLI, UI, StudyTools, and `sbobby-web`.
- No mutable registry, request cache, receipt resolver callback, process-local
  authority map, synthetic `VerifiedRunRecord`, second proof store, or hidden
  task/preference/payload field.

## Exact B2 Receipt Contract

- Replace caller-authored `ProfileTaskExpectation.profile_fingerprint` storage
  with `profile_selection_receipt: ProfileSelectionReceipt`. Preserve a
  read-only `profile_fingerprint` property defined exactly as lowercase SHA-256
  over `b"lesson-worker-profile-selection@1\0" + receipt.to_bytes()`.
- The exact expectation codec contains `profile_selection_receipt` as its
  canonical JSON object and no redundant stored profile fingerprint. Decode by
  `ProfileSelectionReceipt.from_bytes(canonical_json_bytes(value))`, then require
  canonical re-encoding. The existing `ProfileTaskExpectation.fingerprint`
  commits the complete receipt, pins, schema, authority, and validations.
- Existing B2 request/checkpoint/view behavior continues to use the derived
  `profile_fingerprint`. Its exact `profile-sha256:{expectation.fingerprint}`
  task index reference transitively commits the receipt. Do not add the receipt
  to `LessonWorkerRequest.to_public_inputs()`, `GenerationWorkerTask.payload`,
  preferences, continuation summary, evidence references, or public views.

## Immutable Profiled Execution Descriptor

- Add frozen `ProfiledWorkerExecutionDescriptor` in
  `capabilities/worker_adapter.py` with exactly:
  `binding: ProfiledCapabilityBinding`,
  `selection_receipt: ProfileSelectionReceipt`, and
  `profile_expectation_fingerprint: str`.
- Validate the receipt's profile equals `binding.profile`, the expectation
  fingerprint is lowercase SHA-256, and a selected task contains the exact
  `profile-sha256:{profile_expectation_fingerprint}` reference. Binding selection
  still verifies manifest/version/fingerprint, pins, definition, output schema,
  and required authority. A raw profiled binding without its descriptor is not
  executable through the worker adapter.
- `GatewayIsolatedCapabilityRunAdapter` accepts ordinary
  `CapabilityBinding` values and profiled descriptors. Preserve pairwise exact
  identity checks. The descriptor is supplied by the request-scoped C1/C2
  composition reconstructed from the persisted `LessonWorkerRequest`; the
  adapter never discovers or caches it.
- For profiled start, construct execution inputs as the five public fields plus
  only `profile_selection_receipt` containing the receipt's canonical UTF-8 JSON
  text. Reuse one pure helper owned beside the binding and make dispatcher use
  that same helper. Ordinary binding execution inputs remain the public object.

## Public And Execution Commitments

- Add pure `fingerprint_execution_inputs(inputs: JsonObject) -> str` with domain
  `generation-worker-execution-input@1`. A transient
  `ChildCapabilityObservation.execution_input_fingerprint` always binds the
  exact recovered gateway inputs; it is not part of the B1 receipt codec.
- B1 continues to set `GenerationWorkerReceipt.input_fingerprint` to
  `task.payload_fingerprint`. Its service requires the recovered run or
  continuation public projection to equal `task.capability_inputs()` and its
  full input fingerprint to equal the observation's execution commitment.
  Unknown profiled execution keys fail in the adapter before B1 observes them.
- Start and `_completed_observation` receive the exact expected execution object.
  Resume requires `continuation.inputs` to equal that same object and separately
  verifies its public projection. Never replace the recovered run's inputs with
  a sanitized/synthetic public object.
- Extend `VerifiedChildExecutionProof` with
  `execution_input_fingerprint`. Its existing `input_fingerprint` remains the
  public payload fingerprint. The proof JSON includes the new field only when
  it differs from `input_fingerprint`; decode accepts exactly the old field set
  or that set plus the new field, and canonical encoding forbids serializing a
  redundant equal value. Therefore ordinary proof and proof-slot bytes remain
  byte-identical.
- Widen `VerifiedChildProofOwner.create(..., execution_inputs: JsonObject | None
  = None)` and `load(..., execution_inputs: JsonObject | None = None)`. `None`
  means the exact public task inputs for backward-compatible ordinary callers.
  Creation requires recovered `run.inputs` equal the selected exact execution
  object and stores its fingerprint; lookup recomputes and verifies both public
  and execution commitments. Profile adapters must pass the explicit execution
  object. Existing task/authority/receipt/output/prompt/model/validation proof
  checks remain unchanged.

## Dependency And Non-Effect Boundary

- Gateway dependency resolution receives the validated public input object on
  start. On resume, derive the exact public projection from the persisted
  continuation using the manifest property keys, validate it, and pass only
  that projection to the dependency resolver. It must never receive the reserved
  receipt.
- Preserve `ProfiledCapabilityBinding` rejection of any ToolStep, ModelStep, or
  ValidateStep binding that reads `profile_selection_receipt`. No effect,
  dependency resolver, prompt, model request, source executor, validator, state
  write, or provider selector may observe it.
- The receipt records original selection provenance, not current execution
  authority. Do not derive or rewrite selector authority/basis from the child
  `ExecutionContext`. Morphology v1 composition later supplies a persisted
  `TRUSTED_METADATA`/`TRUSTED_MATERIAL` receipt with one source revision; this
  bead validates the generic typed receipt and rejects profile mismatch.

## Recovery And Compatibility

- Same task, descriptor, authority, and retry identity produce byte-identical
  execution inputs and the same run. Changed receipt, profile expectation,
  continuation inputs, or proof lookup conflicts before a second effect.
- Ordinary `CapabilityBinding` start/resume arguments, engine run inputs,
  dependency inputs, observations, B1 task/receipt bytes, durable proof/slot
  bytes, and gateway outcome mapping remain unchanged.
- Do not change the public capability manifest/schema, B1 task or receipt codec,
  run-id domains, public input fingerprint domain, or dispatcher selection
  semantics.

## Verification

- Run the focused tests from the paired brief.
- Then run the existing flashcard dispatcher/binding, B1/B1A, B2 recovery,
  architecture, public-tool contract, and full offline suites.
- Ruff and strict mypy every allowed production file; `git diff --check`.

## Report

Report exact public versus execution commitments, conditional proof codec
compatibility, receipt provenance/recovery, dependency isolation, ordinary-path
golden-byte results, and commands. Do not edit tests/docs, commit, or delegate.
