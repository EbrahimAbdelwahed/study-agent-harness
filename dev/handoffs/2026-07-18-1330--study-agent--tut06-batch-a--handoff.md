# Handoff: TUT-06 Batch A

Date: 2026-07-18 13:30
Area: adaptive-tutor

## Current State

TUT-06B and TUT-06C are complete, reviewed, and fully verified. The next work
must be selected from the remaining dependency-ready TUT-06/GAP beads; do not
reopen runner or file contracts without a concrete compatibility requirement.

## Completed

- Provider-neutral bounded tutor runner and scripted offline adapter.
- Strict v2 host retry receipts and canonical restart-safe continuation bytes.
- Trusted immutable `.txt`/`.md` host snapshots with TTL and bounded atomic
  memory storage.
- Explicit trusted ingestion bridge over the existing ingestion contract.
- Aggregated semantic/security review and approved fixes.

## Remaining

- Re-evaluate the dependency graph before choosing TUT-06D/E or the next GAP
  bead.
- Keep provider integration behind the neutral decision port and preserve the
  trusted authority/file boundaries established here.

## Important Context

- Expired snapshot recapture fails explicitly in v0.1; no renewal or eviction
  policy exists.
- Legacy retry receipts are rejected because they lack host-turn and generation
  binding.
- Capture and lookup remain operational only; canonical source events are
  emitted only by explicit ingestion.

## Verification

- Full pytest: 1612 passed, 2 expected skips.
- Ruff, strict mypy, build, and diff check: passed.
