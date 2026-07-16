# Worker Brief: TUT-04C0B1 isolated worker primitive

## Goal

Implement the generic provider-neutral wrapper that executes one complete child
capability/playbook run in a fresh context and exposes its receipt/view boundary
from ADR-0010 and TUT-04C0B1.

## Allowed Files

- `src/study_agent/workers/__init__.py`
- `src/study_agent/workers/contracts.py`
- `src/study_agent/workers/service.py`
- `src/study_agent/workers/view.py`
- `src/study_agent/ports/worker.py`

## Forbidden Files

- Existing playbook/model/capability files unless a prior architecture audit
  amends this brief, flashcard planning/profile modules, artifact/event/state
  owners, adapters, CLI, configuration, dependencies, tests, specs/docs,
  provider SDKs, and `sbobby-web`.

## Required Contracts

- Strict immutable `GenerationWorkerTask` allowlists task id/kind, prompt/skill/
  playbook/model pins, language/preferences, bounded canonical continuation
  summary, trusted index/evidence references, task payload, and exact output
  schema. Reject unknown, secret-shaped, principal, provider-selection,
  conversation-history, arbitrary-message, canonical-decision, and raw-credential
  fields recursively.
- The task binds the exact child capability id/version, manifest fingerprint,
  complete `VersionPins` (skill, playbook, prompt, model adapter, state contract,
  ordered tool behaviors), definition fingerprint, exact output schema plus its
  fingerprint, and ordered expected validation sequence. Each expectation names
  `step_id`, source `validate_step|structured_output_fallback`, validator id, and
  validator version so repeated validators remain unambiguous. These
  are trusted expectations to compare with the child observation, not selectable
  provider/model instructions inside the task payload.
- Strict `GenerationWorkerReceipt` exists only for terminal completed,
  terminated, cancelled, stale, or failed states and commits task/pins/input/
  output/validator/run fingerprints. Suspension/running are checkpoint/view
  states, never receipts. It exposes no raw reasoning, provider-private response
  id, usage, credential, or malformed attempt.
- Define a minimal operational `GenerationWorkerStore` port for create/CAS/read
  of exact task+receipt state, or reuse an existing generic run store through an
  inward protocol without importing adapters.
- Define an inward `IsolatedCapabilityRunPort` that starts/resumes one named
  existing capability through the gateway with a fresh child execution context.
  It returns a closed typed `ChildCapabilityObservation`, never bare JSON or a
  caller callback. The observation binds capability/version/manifest, child
  `RunId`, actual pins and definition fingerprint, sanitized status/failure,
  output-schema fingerprint, ordered validation/prompt provenance, and contains
  a `CapabilityContinuation` only when suspended or a `VerifiedRunRecord` plus
  gateway-validated output only when completed. The five files define this
  inward boundary; a concrete gateway/dispatcher adapter belongs to B2/C3.
- Public service signatures are
  `start(task, parent: ExecutionContext) -> WorkerCompactView`,
  `resume(task_id, generation, response, parent) -> WorkerCompactView`, and
  `detail(task_id, parent) -> WorkerDetailView`. Task/payload never contain
  authority data. The service derives the child context with the same trusted
  principal kind/id, course, session, and required grants; a deterministic fresh
  correlation id from task id + task fingerprint; a child idempotency key from
  that identity plus capability binding; and `model_run_id=None`. Recording-port
  tests prove authority/session never enter capability inputs, prompts, model
  metadata, or task bytes—not that trusted `ExecutionContext` lacks them.
- The child skill/playbook owns prompt composition, its one `ModelStep`,
  structured-output fallback, and versioned validation. B1 never imports the
  model port, constructs a `ModelRequest`, invokes a validator independently, or
  creates a second model effect. It cannot accept caller-supplied prior messages,
  agent/session history, or a raw dispatcher callback.
- Persist an exact repeatable state machine:
  `pending(task bytes/fingerprint/authority fingerprint)` -> either terminal or
  `suspended(generation, child continuation)` ->
  `resume_claimed(generation, response bytes/fingerprint)` -> either the next
  `suspended(generation+1, continuation)` or
  `terminal(receipt, optional verified detail)`. Create pending atomically before
  delegation. Same identity plus changed bytes/pins/authority conflicts. Pending
  recovery retries `start` with the identical child context; the gateway's
  deterministic retry identity guarantees one child run/model effect. Resume
  CAS-claims the exact response before delegation. CAS losers reload and return
  the identical state or conflict. Terminal retry never delegates. With
  create/CAS/read the service does not promise globally one port invocation
  across a crash/race; it promises one durable child run/model effect.
- A crash in `resume_claimed(n)` retries `port.resume` with the stored exact
  response and continuation. Resume callers must present the generation exposed
  by the compact suspended view; the service rejects a mismatched generation
  before CAS or delegation. Old continuation/response generations conflict.
  A running/in-progress child observation leaves the current recoverable state
  unchanged and returns a compact running view.
- Completed observations must match task-bound manifest/output schema, actual
  pins, definition fingerprint, exact capability inputs, expected ordered
  validator `(id, version)` sequence, typed `continue` dispositions on passing
  recovered validator/fallback receipts, and verified prompt receipt/fingerprint.
  Resume observations and every subsequent continuation retain the stored child
  run id; continuation inputs equal the task payload exactly. The service compares
  provenance but never invokes a model or semantic validator. Missing/tampered
  provenance becomes terminal failed and is never exposed in detail.
- Compact view returns status, task/run identity, fingerprints, failure code,
  and availability of verified detail. A separate typed detail view returns only
  verified structured output to authorized application/UI consumers. Detail
  requires parent context and recomputes the stored authority fingerprint;
  compact views commit to but never reveal principal identifiers.
- Exact codecs perform JSON decode -> freeze/reconstruct -> canonical byte
  equality. Terminal state independently commits the receipt and its child-run,
  output, validator, run, and prompt bindings; decode revalidates those commitments
  against the stored task/pins/input before returning any view. Domain-separated
  fingerprints cover task, payload, output, receipt, and store state. Bounds are:
  canonical task <=128 KiB, payload <=64 KiB,
  output schema <=32 KiB, continuation summary <=16 KiB, verified output <=256
  KiB, stored state <=512 KiB. Recursive forbidden structural keys/paths reject
  secrets, authority, provider selection, messages/history, canonical decisions,
  and raw credentials, including camelCase aliases, without scanning arbitrary
  natural-language values. Failure codes are bounded lowercase machine codes and
  reject free text or sensitive provider/credential metadata before compact views.
- No canonical events, StudyTools, provider types, arbitrary agent loops, or
  long-term memory.

## Verification

- Ruff and strict mypy for new modules.
- Existing model/playbook portability, secret, and architecture/tool tests.
- `git diff --check`.

## Report

Report names, bounds/fingerprint domains, child-context derivation, typed child
observation, store state machine, and proof of one durable child run/model
effect. Do not edit tests, commit, or delegate.
