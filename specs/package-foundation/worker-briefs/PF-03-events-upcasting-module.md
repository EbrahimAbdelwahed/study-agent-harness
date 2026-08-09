# Worker Brief: PF-03

## Assignment

Implement `PF-03` from `specs/package-foundation/slices/PF-03-events-upcasting-module.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01/PF-02/PF-03 slices, and `specs/package-foundation/beads/PF-03-events-upcasting-module.md`
- existing event, state registry/projection, storage protocol, replay tests, and architecture boundaries

## Scope

You may change:

- `src/study_agent/api/events.py`, `src/study_agent/domain/events.py`, `src/study_agent/events/upcasting.py`
- `src/study_agent/kernel/module.py`, `src/study_agent/state/registry.py`, `state/projection.py`, `src/study_agent/ports/storage.py`
- `tests/contract/events/**`, named replay/integration tests, and `tests/architecture/test_import_boundaries.py`

Do not change:

- Package specs, slices, beads, briefs, storage adapter implementations, capability behavior, runtime, metadata, CLI/UI, product modules, workers, telemetry, or dependencies

## Invariants and Requirements

- Preserve append-only event authority and supported history while adding the envelope, upcaster, and module seams.
- Deep-freeze JSON payloads and reject non-JSON values, unknown schemas, invalid versions, self-causation, collisions, and late registration.
- Keep upcasters pure, adjacent, deterministic, and idempotent; replay preserves event, correlation, causation, and sequence identity.
- Let a Host register opaque product contributions without Harness importing a product package.
- Projection, cache, index, snapshot, and operational state remain rebuildable and never canonical.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/events tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_import_boundaries.py tests/architecture/test_capability_gateway_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/domain src/study_agent/events src/study_agent/kernel src/study_agent/state src/study_agent/ports tests/contract/events
git diff --check
```

## Report Back

Return:

- files changed;
- envelope, upcaster, module, and replay behavior implemented;
- exact verification results;
- profile constraints followed;
- unresolved questions;
- follow-up beads needed.
