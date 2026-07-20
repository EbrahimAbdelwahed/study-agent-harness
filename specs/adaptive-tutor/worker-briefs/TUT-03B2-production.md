# Worker Brief: TUT-03B2 production

## Goal

Implement one authority-bound application gateway over trusted capability
bindings and the existing PlaybookEngine checkpoint; do not create another run
record or let the gateway choose a capability.

## Allowed Files

- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/bindings.py`
- `src/study_agent/capabilities/gateway.py`
- `src/study_agent/capabilities/__init__.py`
- `src/study_agent/playbooks/engine.py` only for a resume-generation receipt

## Forbidden Files

- Adapters, providers, model selection, tools and the seven-tool registry,
  canonical events/state, sessions, CLI/UI, built-in capabilities, evals,
  `sbobby-web`, and all tests/docs/specs.

## Fixed Contract

- A trusted immutable binding owns manifest, skill, playbook, pins, output key,
  and a dependency resolver. Construction validates their exact identity,
  schemas, suspension shape, output selection, and manifest fingerprint.
- Public start accepts a host-selected `TutorCapabilityId`, inputs, and
  `ExecutionContext`. Session and idempotency key are mandatory. Verify the
  manifest authority is a subset of the context grant set before any resolver
  or engine effect.
- Derive the authority fingerprint from principal kind/id, course, session, and
  the canonical complete grant set. Derive run ID from capability/manifest,
  authority fingerprint, and idempotency key; never trust these from input.
- A continuation is an immutable typed value binding run/capability/manifest,
  authority/retry identity, definition and suspended-checkpoint fingerprints,
  dialogue step/index, exact inputs, pins, and read dependencies.
- Add an optional, validated resume-generation fingerprint to the completed
  DialogueStep trace so a retry can prove which suspended checkpoint its
  response claimed. Existing checkpoint bytes and old dialogue receipts remain
  readable.
- Exact start/resume duplicates inspect persisted bindings and converge without
  another effect. A changed input or dialogue response conflicts. A RUNNING
  winner raises a retryable `in_progress` gateway error and is not relabelled
  failed.
- Successful terminal outcomes include `VerifiedRunRecord` from `recover()`.
  Suspended outcomes include only the dialogue request and continuation.
  Cancelled/failed/stale carry no verified output. `stale` is emitted only for
  `STALE_READ_DEPENDENCY`; all other incompatibility fails closed.
- Keep the closed public outcome statuses from TUT-03A. The gateway never ranks,
  recommends, or selects a capability and never calls a provider-specific API.

## Verification

- Ruff and strict mypy on changed source, focused gateway/engine tests, import
  architecture and seven-tool parity, full offline suite, and diff check.
