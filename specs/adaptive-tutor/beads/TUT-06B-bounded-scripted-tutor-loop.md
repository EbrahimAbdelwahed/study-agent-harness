# Task Bead: TUT-06B bounded scripted tutor loop

Status: Blocked on TUT-06A
Priority: P0
Type: tracer-bullet
Depends On: TUT-06A

## Outcome

A deterministic provider-neutral runner uses a scripted decision adapter and
the existing capability gateway to execute a bounded tutor turn with explicit
interruption, exact retry, stale refresh, and continuation behavior.

## Acceptance Criteria

- [ ] `TutorHostRunner` receives the decision port, snapshot/evidence readers,
  one gateway-facing port, trusted authority factory, and explicit limits. It
  contains no provider branch and owns no canonical study behavior or state.
- [ ] Scripted and later live adapters enter through the same
  `TutorDecisionPort`; the runner always calls the same gateway
  discover/start/resume contract.
- [ ] Separate positive limits bound logical decisions, provider attempts per
  decision, stale refreshes, and total emitted learner/assistant text. Budget
  exhaustion returns a typed non-success outcome and cannot expose a completed
  capability result.
- [ ] Interruption is checked before and after decision and gateway boundaries.
  Interrupted execution performs no later effect and returns only a sanitized
  host receipt plus any already-issued opaque continuation descriptor.
- [ ] The trusted host supplies principal, course/session, grants, correlation,
  and retry identity out of band. The runner validates a decision against the
  currently advertised manifest before calling the gateway.
- [ ] An exact action retry preserves action fingerprint, inputs, authority,
  and idempotency identity. Changed action content requires a new trusted host
  action identity; it can never be treated as an exact retry.
- [ ] `IN_PROGRESS` remains explicitly retryable with the same action identity.
  Completed, suspended, terminated, cancelled, stale, and failed gateway
  outcomes remain distinct host outcomes.
- [ ] A stale start or resume discards that decision generation, reacquires both
  sequence-consistent views, and requires a fresh decision under a new action
  identity. It never blindly resumes a stale continuation.
- [ ] A suspended capability exposes only its bounded dialogue request and
  opaque continuation fingerprint. Exact continuation bytes and trusted
  execution context remain host-side.
- [ ] Offline tests cover direct completion, start-suspend-learner-resume,
  exact lost-output retry, stale refresh, in-progress retry, every terminal
  outcome, step exhaustion, and interruption at each effect boundary.

## Verification

- Scripted runner unit/contract/integration tests; gateway call recordings;
  deterministic context and action receipts; no-network default suite;
  architecture gates; Ruff; strict mypy.
