# Task Bead: TUT-03B2 authority-bound capability gateway

Status: Done
Priority: P0
Type: expand
Depends On: TUT-03B1

## Outcome

One application gateway starts or resumes a host-selected registered capability
with convergent retries and no second operational run record.

## Acceptance Criteria

- [x] Trusted binding matches manifest fingerprint/version, skill, playbook,
  pins, output selection, suspension shape, and dependency builder.
- [x] Start derives run identity from capability/manifest, exact authority scope,
  and idempotency key; inputs are schema-valid and engine-bound before effects.
- [x] Continuation binds the exact suspended checkpoint generation, dialogue,
  inputs, pins, dependencies, authority, and retry identity.
- [x] Exact duplicate start/resume returns inspected or recovered state without
  repeating effects; changed input/response conflicts.
- [x] Concurrent resume has one CAS winner; a loser observes the winner, and a
  still-running winner returns retryable `in_progress` without terminal claims.
- [x] Completed/terminated outcomes contain verified recovery; suspended carries
  continuation; cancelled/stale/failed never carry verified output.
- [x] Stale maps only dependency drift. Authority, manifest, pin, token, and
  checkpoint incompatibility fail closed before effects.
- [x] Gateway never selects a capability or changes the seven StudyTools.

## Verification

- Gateway value/authority/idempotency contracts, process-loss and concurrent
  resume integration, architecture/tool parity, and full gates.
