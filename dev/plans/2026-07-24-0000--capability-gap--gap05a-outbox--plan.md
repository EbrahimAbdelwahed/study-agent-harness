# Plan: GAP-05A strict redacted harness outbox

Date: 2026-07-24 00:00
Area: capability-gap feedback

## Goal

Add a provider-neutral, local-only outbox that serializes a strict, redacted
snapshot of capability-gap aggregates with deterministic bytes and explicit
publication semantics. Source aggregates remain durable and no network or
Flywheel operation is reachable from this package.

## Scope

- In scope: `feedback` outbox contracts/service, the capability-gap port and
  SQLite enumeration/state transition needed by the service, focused tests,
  and this plan/log/handoff.
- Out of scope: hosted transports, devkit/Flywheel/GitHub, learner/course
  events, provider adapters, arbitrary filesystem/network effects, and new
  dependencies.

## Contract / invariants

1. `GapOutboxBundleV1` and `GapOutboxRecordV1` use exact allowlisted fields,
   canonical JSON bytes, versioned schemas, and a domain-separated SHA-256
   bundle fingerprint. Records contain only aggregate dimensions, closed
   enums, counts, safe trusted fingerprints, versions, timestamps, and state.
2. Decoders reject unknown fields/schema, noncanonical bytes, tampering,
   key/payload mismatch, invalid fingerprints, and duplicate keys with
   conflicting payloads. Portable bytes cannot represent text, paths,
   credentials, principals, provider-private data, commands, or executables.
3. A trusted local export service requires an explicit call, snapshots records
   in deterministic key order, writes bytes through an injected local
   publisher, and marks `EXPORTED` only after durable publication succeeds.
   Repeated publication of an unchanged snapshot is byte-identical and source
   aggregates are retained. Failed publication leaves records pending.

## Files

- Allowed: `src/study_agent/feedback/**`,
  `src/study_agent/ports/capability_gap.py`,
  `src/study_agent/adapters/sqlite/capability_gap_store.py`, focused tests,
  this plan and a completion log.
- Forbidden: sbobby-web, canonical course event store/schema, capability
  manifests/StudyTools, provider/model adapters, hosted transport, network,
  Flywheel/devkit/GitHub, and dependency changes.

## Verification

- Focused GAP-05A pytest tests (golden bytes, roundtrip, rejection,
  restart/idempotency and retention).
- Ruff on changed source/tests, strict mypy on changed source, and `git diff
  --check`; run the broader offline suite when the orchestrator integrates.

## Plan review

The design keeps the export boundary outside canonical events, exposes no
transport implementation, and uses publication-before-state ordering to avoid
false `EXPORTED` claims across crashes. Any requirement for a new dependency,
provider-specific data, or hosted delivery stops this bead for orchestration.
