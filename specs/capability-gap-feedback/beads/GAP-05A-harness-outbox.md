# Task Bead: GAP-05A strict redacted harness outbox

Status: Approved — blocked on GAP-02 implementation
Priority: P1
Type: tracer-bullet
Depends On: GAP-02

## Outcome

A maintainer can explicitly export pending structured aggregates as a strict,
credential-free local bundle without any network or Flywheel dependency.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Portable local-only boundary and privacy guarantees.

## Grilling Evidence

- Session/artifact: accepted ADR-0011 and GAP-01 codec evidence.
- Decision state: scope approved 2026-07-18; implementation dependency remains.
- ADR/glossary changes: none expected.

## Worker Profile

reuse `implementer`; independent `security-reviewer`

## What To Do

- Define/version strict bundle and per-gap canonical record schemas.
- Export only structured taxonomy, GapKey dimensions, counts, trusted receipt
  fingerprints, contract versions, and resolution/export status.
- Require explicit trusted local action; pin deterministic bytes and idempotent
  export marking without deleting the source aggregate.

## Acceptance Criteria

- [ ] Bundle cannot express learner/model free text, material/path/filename,
  credential/principal/provider-private data, command, or executable payload.
- [ ] Tamper, unknown schema, key/payload mismatch, and collision fail closed.
- [ ] Same snapshot exports byte-identically and performs no network operation.
- [ ] Harness core imports no devkit/Flywheel/GitHub dependency.

## Verification

- Golden bytes, roundtrip/tamper/collision/redaction, process restart, dependency
  firewall, Ruff, strict mypy, and full offline tests.

## Out Of Scope

- Devkit import, reproduction, proposal generation, or decision requests.
