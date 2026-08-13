# Plan: capability-gap local MVP wave

Date: 2026-07-21 19:00
Area: capability-gap feedback

## Goal

Complete the local, offline capability-gap loop from strict observation through
redacted outbox, untrusted import/reproduction, immutable proposal/decision,
and accepted-only promotion. Preserve the existing essential tracer and keep
the core independent of network, Flywheel, GitHub, and course state.

## Scope

- In scope: `src/study_agent/feedback/**`, `src/study_agent/ports/capability_gap.py`,
  `src/study_agent/adapters/sqlite/capability_gap_store.py`, a local outbox
  adapter, focused tests, and narrowly required local devkit boundary modules.
- Out of scope: hosted transport, concrete converters, TUT-07/TUT-08,
  GitHub/network effects, automatic issue/goal/code creation, and study-plane
  changes.

## Approach

1. Reuse and harden existing GAP-01/02 contracts, service, host tool, and
   SQLite registry; add bounded local lifecycle/rate/resolution and workaround
   receipt contracts only where required by the later beads.
2. Add source-format tracing that consumes typed unsupported-extension evidence
   and emits only closed observation metadata.
3. Add strict versioned redacted outbox contracts/export and local persistence.
4. Add an offline devkit-facing importer/reproducer, proposal/decision records,
   and accepted-only promotion records using test doubles that cannot dispatch.
5. Add adversarial integration coverage and update owned bead statuses only
   after focused/full verification.

## Invariants

- Host context is the sole authority for identities, receipts, grants,
  idempotency, and timestamps; model payloads are closed enums only.
- Portable bytes contain no free text, path, filename, source body, secret,
  command, provider-private value, or executable payload.
- Gap keys are domain-separated SHA-256 over canonical dimensions; operation
  kinds never collapse solely by target family.
- Exact retries and concurrent/process-restart replays converge; export is
  explicit and byte-stable; import is untrusted and offline-only.
- Only an accepted immutable proposal may produce approved workflow records;
  test doubles never invoke external goals, dispatch, network, or GitHub.

## Verification

- Focused feedback/outbox/devkit tests first.
- Ruff and strict mypy on changed source.
- Full offline pytest and `git diff --check` where feasible.

## Stop / escalation

Stop and report if a change requires a new public API, schema outside the
allowed local plane, external dependency, hosted adapter, concrete converter,
or mutation of the seven StudyTools/canonical course event boundary.
