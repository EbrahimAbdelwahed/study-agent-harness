# Worker Brief: TUT-04C0B1A gateway-worker proof adapter

## Goal

Implement the generic gateway-to-B1 adapter and one atomic sanitized
verified-child execution-proof path for trusted downstream owners.

## Allowed Files

- `src/study_agent/capabilities/worker_adapter.py`
- `src/study_agent/capabilities/{__init__,gateway,dispatch}.py`
- `src/study_agent/workers/{__init__,proof,service}.py`
- `src/study_agent/ports/{__init__,worker}.py`
- `src/study_agent/playbooks/{__init__,engine}.py`

## Forbidden Files

- B1 contracts/views, capability bindings/contracts, playbook AST/runtime,
  flashcard/exam/artifact/state/event owners, adapters, CLI, dependencies,
  tests, specs/docs, provider SDKs, StudyTools, `sbobby-web`, provisional C1/C2.

## Public Pure Helpers and Resume Shape

- Export `playbook_definition_fingerprint(definition) -> str` by renaming the
  existing engine implementation without changing its domain/output. Engine,
  gateway, and dispatch call it directly; remove private imports and
  `_bound_definition_fingerprint`/equivalent wrappers.
- Export `generation_worker_authority_fingerprint(task, parent) -> str` from the
  worker package by renaming the current B1 algorithm without changing bytes.
  B1 and proof call this exact helper.
- Export the existing pure B1 derivation as
  `generation_worker_child_context(task, parent) -> ExecutionContext` from the
  worker package without changing correlation/idempotency domains or bytes. B1
  itself calls this public helper. Downstream proof consumers use it instead of
  duplicating child-context derivation.
- Widen the inward port only to
  `resume(task, continuation, response, context)`. B1 passes the exact task
  decoded from durable state on initial resume and every claimed-response retry.
  The adapter checks it against the continuation. No registry/cache/callback or
  caller reconstruction is allowed.

## Gateway Adapter

- `GatewayIsolatedCapabilityRunAdapter` receives trusted gateway, immutable
  bindings, and proof owner; never a model/provider object. Start/resume call the
  gateway exactly once after verifying task/continuation manifest, pins,
  definition, schema, and authority.
- Map completed/suspended/terminated/cancelled/stale/failed exactly; retryable
  `IN_PROGRESS` becomes running and other errors become bounded failure codes.
- Reconstruct observation prompt and ordered validate/fallback receipts only
  from the engine-recovered `VerifiedRunRecord` plus bound playbook. Require one
  exact completed model prompt receipt and exact expected validations; reject
  missing/extra/duplicate/reordered/tampered provenance without rerunning it.
- Observation exposes only gateway-validated public output. The transient
  completed observation still carries the exact `VerifiedRunRecord` for B1.

## Sanitized Durable Proof

- Exact-codec `VerifiedChildExecutionProof` contains exactly: child run and
  completed status; definition fingerprint and pins; capability-input
  fingerprint only; exact public output plus fingerprint; ordered
  `ReadDependency`s; allowlisted completed `ToolStep` outputs; one technical
  model receipt; one prompt receipt; ordered validation receipts. No complete
  `VerifiedRunRecord`, raw inputs/traces/timestamps/reasons, or other outputs.
- Each tool output binds step id, output key, tool id/version, canonical value,
  and fingerprint and must correspond to one completed declared `ToolStep`.
- Technical model receipt is limited to adapter id/version, model id, nullable
  response id, and optional exact input/output token usage. E1 needs these
  observed provenance fields. Forbid messages/request bodies, endpoints,
  headers, credentials, SDK objects, and provider policy.
- `VerifiedChildProofStore` owns one atomic canonical slot keyed only by child
  `RunId`. The slot binds task fingerprint, authority fingerprint, expected B1
  completed `GenerationWorkerReceipt` fingerprint, and proof. Identical create
  is retry; any competing field conflicts. No staging/final tables or CAS
  promotion exist. It persists neither `GenerationWorkerTask` bytes nor raw
  capability inputs.
- Before returning completed, the trusted adapter/owner path receives the exact
  engine-recovered `VerifiedRunRecord` and bound playbook, verifies its run
  fingerprint against the expected B1 receipt, and derives the sanitized proof
  internally. It must not accept caller-authored dependency/tool/model fields.
  The derived proof must exactly match recovered read dependencies, completed
  declared tool outputs, and the technical model receipt including nullable
  response id and usage. It validates proof codec/512-KiB bound and atomically
  creates/observes the slot. Codec/oversize/store/conflict failure
  returns sanitized FAILED, so B1 cannot persist completion without proof. Crash
  after create recovers by identical gateway/owner retry.
- `VerifiedChildProofOwner.load(task, run_id, receipt, context)` requires the exact
  `GenerationWorkerTask`, verifies its fingerprint against the owner slot, and
  recomputes authority with the shared helper using the supplied exact child
  context. It then verifies receipt plus
  every task/pin/input/output/validator/run/prompt commitment against the slot.
  Only exact task plus completed receipt returns a sanitized view. Never recover
  task/raw inputs from proof storage. Proof is operational, read-only,
  event-free, and absent from B1 compact/detail/tutor views.
- A nullable technical model `response_id` is valid provider-neutral observed
  provenance. B1A preserves null exactly; it neither invents an id nor rejects a
  verified execution solely because the adapter supplied none. E1 owns any
  required follow-up change to its artifact provenance contract.

## Verification

- Existing gateway/B1 receipt/state bytes and public views remain unchanged;
  only inward resume and shared pure helpers widen.
- Clean-process imports work in both orders (`study_agent.workers` first and
  `study_agent.capabilities` first); the adapter must not re-enter a partially
  initialized public package through eager cross-package exports.
- Focused adapter/proof/B1 regression tests, public tool contract, Ruff, strict
  mypy, full offline pytest, and `git diff --check`.

## Scope Decision

One fresh-context technical bead; no pedagogy, canonical owner, provider
abstraction, or ADR change.
