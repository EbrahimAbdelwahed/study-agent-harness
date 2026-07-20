# Task Bead: TUT-04C0B1B profiled worker execution commitments

Status: Done
Priority: P0
Type: expand
Depends On: TUT-04C0B1A, TUT-04C0B2

## Outcome

One request-scoped, provider-neutral bridge executes a profiled flashcard worker
with five public task inputs plus one trusted non-effect profile-selection
receipt, while preserving B1 task/receipt identity and B1A proof recovery.

## Acceptance Criteria

- [ ] `ProfileTaskExpectation` persists the exact canonical
  `ProfileSelectionReceipt`; its domain-separated profile fingerprint and the
  existing expectation/index commitments bind those exact receipt bytes across
  checkpoint/restart. The receipt never enters the public task payload.
- [ ] An immutable `ProfiledWorkerExecutionDescriptor` binds one exact
  `ProfiledCapabilityBinding`, selection receipt, and profile-expectation
  fingerprint. It rejects profile or task-reference drift without a registry,
  callback, cache, provider object, or process-local authority state.
- [ ] `GenerationWorkerTask.capability_inputs()` and the B1 completed receipt's
  `input_fingerprint` remain exactly the five public manifest inputs. Gateway
  execution inputs add only canonical `profile_selection_receipt` for profiled
  bindings and are committed by a separate domain-separated execution-input
  fingerprint.
- [ ] Start, suspended continuation, resume, completed observation, B1
  verification, proof creation, and proof lookup all verify the same exact
  execution inputs. The durable proof codec serializes the extra execution
  fingerprint only when it differs from the public-input fingerprint, so the
  ordinary `CapabilityBinding` task/receipt/proof bytes remain unchanged.
- [ ] Dependency resolution receives only the public manifest projection on
  start and resume. Existing binding validation continues to forbid ToolStep,
  ModelStep, and ValidateStep bindings from reading the reserved receipt; it
  cannot affect model/tool/validator inputs, read sets, or provider selection.
- [ ] A morphology descriptor accepts only a valid persisted selection receipt.
  The v1 anatomy path uses `TRUSTED_METADATA`, `TRUSTED_MATERIAL`, and one exact
  source `RevisionId`; `DEFAULT/HOST` morphology and worker-context-derived
  selection provenance fail closed.
- [ ] Crash/retry reconstructs the descriptor from the persisted B2 request,
  reuses byte-identical execution inputs, and observes the same gateway run and
  proof slot without repeating a model effect.
- [ ] Ordinary non-profiled capabilities preserve their public/execution input
  equality, continuation behavior, run identity, B1 receipt bytes, proof bytes,
  dependency inputs, and outcome mapping.

## Scope

- B2 profile-expectation receipt ownership, one immutable gateway-worker
  execution descriptor, exact public/execution input verification, conditional
  proof commitment, and public-only dependency projection.
- No C1/C2 prompt or pedagogy implementation, new task payload field, public
  manifest change, provider adapter, artifact/event/state owner, StudyTool,
  dependency, UI, or `sbobby-web` change.

## Verification

- Exact receipt/expectation codecs and fingerprints, profiled start/resume/proof
  recovery, ordinary-path golden bytes, dependency isolation, task/profile/
  receipt drift, architecture boundaries, Ruff, strict mypy, and full offline
  gates.

## Grilling Evidence

`ProfiledCapabilityBinding` requires the reserved receipt as a playbook input,
but B1/B1A originally required recovered run inputs to equal the public task
payload. Injecting the receipt only in C1 would therefore fail completion and
proof creation. Persisting original selection provenance is also necessary
because morphology cannot truthfully derive a valid receipt from the service
worker context.
