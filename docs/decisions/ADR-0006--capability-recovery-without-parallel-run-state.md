# ADR-0006: Recover capability runs without parallel operational state

Date: 2026-07-15
Status: Accepted

## Context

The capability gateway must make start and resume retries convergent while
binding trusted authority, capability identity, inputs, pins, read dependencies,
and dialogue generation. `PlaybookEngine` already persists every execution
input, pin, dependency, output, trace, and status behind atomic run-store CAS,
but only exposes verified recovery for successful terminal runs.

A second gateway run record would duplicate checkpoint facts and introduce a
two-record coordination failure without making canonical study state safer.
Generic process interruption also cannot truthfully prove that an in-flight
tool or model operation was cancelled.

## Decision

- Keep the existing PlaybookEngine checkpoint as the sole operational run
  record. Do not add a gateway metadata table or parallel run store.
- Add a read-only engine inspection value that validates canonical checkpoint
  bytes and exposes status, exact bindings, checkpoint/definition fingerprints,
  dialogue generation, outputs, and traces. Inspection never confers verified
  success; `recover()` remains the only successful-run proof.
- Persist `cancelled` only when the model transport explicitly returns
  `ModelErrorCode.CANCELLED` or `ModelFinishReason.CANCELLED`. Do not translate
  `asyncio.CancelledError`, SIGINT, or process loss into a cancelled run.
- Derive a capability run ID from capability/manifest identity, the trusted
  authority scope, and the host idempotency key. Changed input with the same
  identity collides with the existing run and fails closed.
- A continuation binds the exact suspended checkpoint fingerprint,
  definition/manifest fingerprints, dialogue step and index, frozen inputs,
  pins, read dependencies, authority fingerprint, and retry identity.
- On duplicate start or resume, inspect first and return the already-observed
  state without effects. A repeated dialogue response must match the persisted
  DialogueStep output and suspended generation; a different response conflicts.
- A duplicate observed while the winner is still `running` is a retryable
  non-success `in_progress`, not a persisted failed or cancelled claim.
- `stale` means only `STALE_READ_DEPENDENCY`. Authority, input, pin, manifest,
  token, or checkpoint incompatibility is a failed rejection.

## Consequences

- The gateway reuses engine CAS and recovery rather than becoming a second
  runtime or state owner.
- Suspended and interrupted runs are inspectable without weakening
  `VerifiedRunRecord`.
- Confirmed transport cancellation is distinguishable from failure, while
  ambiguous process loss remains visibly `running` and is never auto-replayed.
- Continuations are larger typed operational values, but contain no canonical
  learner facts and can be reconstructed and verified without another database.

## Alternatives Considered

- Separate capability-run metadata record: rejected because checkpoint facts
  would have two owners and record creation cannot be atomic with engine CAS.
- Encode authority/retry identity as fake read dependencies: rejected because
  it weakens the meaning of dependency drift and `stale`.
- Treat generic interruption as cancelled: rejected because effects may already
  have happened and the transport may still be running.
