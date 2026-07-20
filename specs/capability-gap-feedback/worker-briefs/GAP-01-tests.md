# Worker Brief: GAP-01 tests

## Assignment

Independently test `GAP-01` contracts, service, store, replay, privacy, and
architecture boundaries.

## Read First

- `docs/decisions/ADR-0011--capability-gap-observation-and-promotion.md`
- `specs/capability-gap-feedback/README.md`
- `specs/capability-gap-feedback/beads/GAP-01-report-contracts-registry.md`
- completed GAP-01 production report and changed modules
- existing SQLite/store, canonical-codec, architecture, and tool-parity tests

## Scope

You may change:

- `tests/unit/feedback/test_capability_gap_contracts.py`
- `tests/unit/feedback/test_capability_gap_service.py`
- `tests/integration/test_capability_gap_sqlite.py`
- `tests/architecture/test_capability_gap_boundaries.py`

Do not change production files, existing tests/fixtures, dependencies,
configuration, docs/specs, CLI, devkit, or `sbobby-web`.

## Requirements

- Pin exact enum/schema/codecs and `GapKeyV1` canonical bytes/fingerprint.
- Prove PDF `extract_text` and `preserve_tables` remain distinct while separate
  equivalent observations aggregate.
- Prove exact retry does not increment; a new idempotency identity increments
  once; CAS races and process restart converge byte-identically.
- Cover verified receipts, `unverified_request`, forged/missing/mismatched receipt
  fingerprints, key collision, tamper, unknown fields, non-canonical bytes,
  bool/int confusion, invalid transitions, and stale writes.
- Negative fixtures attempt free text, filename/path, source body, prompt,
  secret, command, executable payload, provider selector, priority, severity,
  assignee, issue body, principal/session identity, and caller-authored IDs.
- Prove the SQLite registry is operationally separate: no course event, reducer,
  learner snapshot, artifact, capability run, or canonical export changes.
- Architecture fixtures preserve exactly seven StudyTools and forbid imports from
  model/prompt/playbook/capability, network/HTTP, devkit/Flywheel/GitHub, product,
  and provider SDK packages.

## Verification

Run focused pytest first, then Ruff, strict mypy, relevant architecture/tool
parity, full offline pytest if practical, and `git diff --check`.

## Report Back

Return files changed, behaviors/hostile cases pinned, commands/results,
production mismatches, and residual risks. Confirm production was not edited.
Do not commit or delegate.
