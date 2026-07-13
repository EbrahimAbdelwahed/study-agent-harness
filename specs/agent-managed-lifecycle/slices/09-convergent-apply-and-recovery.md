# Slice 09: Convergent apply and recovery

Release: 0.2
Depends on: slices 05–08

## Contract unlocked

An agent can apply an expected plan through existing services, recover after
interruption, and prove convergence without direct persistence writes or global
transaction fiction.

## API seam

- `LifecycleService.apply(plan, snapshots, authority)`, where authority is
  trusted host input and never manifest data.
- CLI `manifest apply [PATH] --expect-plan SHA256`.
- Structured receipt: completed, noop, degraded, remaining, conflict, and
  observed high-water results.

Before each action, apply revalidates config, manifest, snapshots, and affected
course high-water. Stale observation is a retryable conflict through existing
expected-sequence/CAS semantics; no global lock is claimed. Each mutation uses
the existing service boundary. Retrieval remains discardable operational state.

After interruption or lost output, the exact protocol is `status → plan → apply
--expect-plan NEW_SHA`. The old SHA performs no new mutation unless its next
action is still current and verified unfulfilled; otherwise it fails stale.

## Runnable checkpoint

Apply the normative manifest, rerun to zero-event noop, interrupt after each
action boundary, execute the recovery protocol, replay, doctor, and export.

## Verification

- No direct event/projection/blob/SQLite writes outside existing owners.
- Second converged apply appends zero events.
- Concurrent append invalidates only the affected action; completed actions and
  remaining work are reported honestly.
- Crash/reopen/re-plan/apply creates no duplicate course/source event.
- Index failure after source commit returns `applied_degraded`; doctor repairs it.
- CLI uses SERVICE principal `study-agent-cli`, plan-derived correlation, and
  per-action idempotency; embedding hosts pass `LifecycleAuthority` explicitly.
- Lifecycle never calls a model/provider; full Python 3.12/3.13 release gates,
  architecture audit, and security review pass.

## Human review checkpoint

All-or-nothing multi-course behavior, deletion, config rewriting, or remote
acquisition requires reslicing and a separate decision.
