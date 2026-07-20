# Task Bead: TUT-06B bounded scripted tutor loop

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-06A

## Outcome

A deterministic provider-neutral runner uses a scripted decision adapter and
the existing capability gateway to execute a bounded tutor turn with explicit
interruption, exact retry, stale refresh, and continuation behavior.

## Acceptance Criteria

- [x] `TutorHostRunner` receives the decision port, snapshot/evidence readers,
  one gateway-facing port, trusted authority factory, and explicit limits. It
  contains no provider branch and owns no canonical study behavior or state.
- [x] Scripted and later live adapters enter through the same
  `TutorDecisionPort`; the runner always calls the same gateway
  discover/start/resume contract.
- [x] Separate positive limits bound logical decisions, provider attempts per
  decision, stale refreshes, and total emitted learner/assistant text. Budget
  exhaustion returns a typed non-success outcome and cannot expose a completed
  capability result.
- [x] Interruption is checked before and after decision and gateway boundaries.
  Interrupted execution performs no later effect and returns only a sanitized
  host receipt plus any already-issued opaque continuation descriptor.
- [x] The trusted host supplies principal, course/session, grants, correlation,
  and retry identity out of band. The runner validates a decision against the
  currently advertised manifest before calling the gateway.
- [x] An exact action retry preserves action fingerprint, inputs, authority,
  and idempotency identity. Changed action content requires a new trusted host
  action identity; it can never be treated as an exact retry.
- [x] `IN_PROGRESS` remains explicitly retryable with the same action identity.
  Completed, suspended, terminated, cancelled, stale, and failed gateway
  outcomes remain distinct host outcomes.
- [x] A stale start or resume discards that decision generation, reacquires both
  sequence-consistent views, and requires a fresh decision under a new action
  identity. It never blindly resumes a stale continuation.
- [x] A suspended capability exposes only its bounded dialogue request and
  opaque continuation fingerprint. Exact continuation bytes and trusted
  execution context remain host-side.
- [x] Offline tests cover direct completion, start-suspend-learner-resume,
  exact lost-output retry, stale refresh, in-progress retry, every terminal
  outcome, step exhaustion, and interruption at each effect boundary.

## Verification

- Scripted runner unit/contract/integration tests; gateway call recordings;
  deterministic context and action receipts; no-network default suite;
  architecture gates; Ruff; strict mypy.

## Plan Review Decisions

- `SuspendedCapabilityOutcome` must expose the exact public dialogue response
  schema already owned by the selected `DialogueStep`; the runner cannot inspect
  private bindings/playbooks or invent a permissive schema.
- Existing retryable `CapabilityGatewayError(IN_PROGRESS)` maps to a distinct
  host outcome; the capability outcome union is not extended for in-progress.
- Exact continuation bytes plus their trusted execution context live only in an
  injected operational host store. Model-facing context receives the existing
  opaque descriptor.
- Runner calls carry a trusted opaque host-turn id, optional retry receipt, and
  optional explicitly selected pending fingerprint. Start and dialogue-answer
  actions each receive their own receipt; resume still uses the original stored
  execution context required by continuation authority.
- One serialized Luna implementer follows the detailed production brief; review
  is aggregated after TUT-06C.

## Worker Brief

- [Production and focused tests](../worker-briefs/TUT-06B-production.md)
