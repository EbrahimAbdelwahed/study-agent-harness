# Slice 08: Deterministic plan and status

Release: 0.2
Depends on: slices 05–07

## Contract unlocked

An agent can compare desired intent and verified snapshots with canonical state
and receive a stable plan or drift report without mutation.

## API seam

- `study_agent.lifecycle.planner`: pure desired-versus-observed planner.
- `LifecyclePlanV1`: manifest fingerprint, source checksums, observed per-course
  high-water sequences, ordered actions, conflicts, warnings, and fingerprint.
- CLI `manifest plan [PATH]` and `manifest status [PATH]`.

Order is repository, courses by ID, then sources by `(course_id, source_id)`.
Actions are initialize, create course, ingest revision, rebuild index, noop,
warning, or conflict. Removal is warning-only. The required repository path is
resolved only through slice 06; absent target plans exact config initialization,
and an incompatible/differently configured target is a conflict.

## Runnable checkpoint

Golden JSON plans for absent, converged, changed-source, immutable-course
conflict, stale/missing index, and config mismatch states.

## Verification

- Planner has no I/O and is deterministic across process restart.
- Plan/status append no event, write no run/index row, and call no model/network.
- Same state/snapshots yield byte-identical plan fingerprints.
- Course mismatch is conflict; source change is one immutable revision.
- Status distinguishes converged, canonical conflict/drift, source drift, and
  operational degradation.

## Human review checkpoint

Reject executable callbacks, raw domain events, or an action without one owner
and deterministic verification.
