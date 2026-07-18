# Task Bead: GAP-05B devkit import, deduplication, and reproduction

Status: Approved — blocked on GAP-05A implementation
Priority: P1
Type: tracer-bullet
Depends On: GAP-05A

## Outcome

The devkit imports one hostile bundle deterministically, maps each gap key to an
intake candidate, checks active work, and records reproducible or explicitly
unreproducible evidence without creating a proposal decision or implementation.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Safe one-way factory intake, active-work deduplication, and reproduction.

## Grilling Evidence

- Session/artifact: GAP-05A accepted schema and existing Flywheel intake rules.
- Decision state: scope approved 2026-07-18; implementation dependency remains.
- ADR/glossary changes: none expected.

## Worker Profile

reuse `implementer`; independent `security-reviewer`

## What To Do

- Treat bundle data strictly as untrusted evidence, validate canonical bytes,
  and accept a trusted `delivery_import_id` only as import idempotency context.
  Local imports derive the equivalent ID from a fixed local sender scope and
  bundle fingerprint.
- Make each delivery contribute at most once, then create/aggregate one intake
  candidate per gap key, linking exact duplicates and active
  specs/beads without auto-merging independent operation kinds.
- Run only allowlisted offline reproduction fixtures and record
  `reproduced|not_reproduced|not_reproducible_from_export` with evidence.

## Acceptance Criteria

- [ ] Reimport is idempotent; tampered/unknown/collision bundles fail before any
  workflow mutation.
- [ ] Distinct delivery IDs containing the same GapKey contribute independently
  once to the same candidate/aggregate; sender scope and delivery ID never enter
  reproduction or proposal evidence.
- [ ] Similar format families with different operation kinds remain separate.
- [ ] Import creates no approved spec/bead, decision, goal, code, dependency,
  GitHub issue, network effect, or worker dispatch.

## Verification

- Hostile import, duplicate/active-work, reproduction-status, retry/process-loss,
  dependency-direction, and devkit validation tests.

## Out Of Scope

- Technical option generation, decision requests, or promotion.
