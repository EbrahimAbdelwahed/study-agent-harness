# Task Bead: PF-03 Events, upcasting, and module

Status: Open
Priority: P1
Type: task
Depends On: PF-01, PF-02

## Outcome

Canonical events use one frozen versioned envelope, supported historical
payloads upcast deterministically, and host contributions register through an
immutable `KernelModule` before runtime start.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-03 envelope, payload, replay, upcaster, module, collision, and closure contracts in `specs/package-foundation/slices/PF-03-events-upcasting-module.md`.
- README invariants for one canonical append-only stream, deterministic replay, and no product import.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-03-events-upcasting-module.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `event-state-kernel-worker`

Rationale:

The bead extends the existing event/replay kernel with versioning and explicit
module closure, matching the profile's append-only and replay quality gates.

## Context

Downstream hosts need one generic stream contract that preserves supported
history and accepts opaque host contributions without source coupling. The
envelope, pure upcaster registry, and closed module registry provide that seam.

## Invariants

- `EventEnvelope` fields, IDs, timestamps, actor, schema version, and deep-frozen JSON payload are validated before append.
- Namespaced event types and positive schema versions are canonical; payloads reject NaN, infinity, bytes, executable objects, and provider objects.
- The append-only event stream is canonical; projections, snapshots, indexes, caches, and operational runs never write canonical facts.
- Upcasters advance only one adjacent version, are pure/idempotent, and preserve event, correlation, and causation IDs.
- Modules are immutable, explicitly registered, sorted, and closed before runtime; duplicate owners, unknown schemas, and late registration fail with typed errors.

## What To Do

- Implement the frozen envelope, canonical codec, sequence/actor validation, and safe payload freezer.
- Implement deterministic adjacent-version `EventUpcasterRegistry` and mixed-version replay fixtures.
- Implement immutable `KernelModule` contributions and registry closure/collision checks.
- Integrate the event-store protocol while preserving existing replay and product-opaque registration.

## Likely Allowed Files / Packages

- `src/study_agent/api/events.py`, `src/study_agent/domain/events.py`: envelope and codecs.
- `src/study_agent/events/upcasting.py`: pure upcaster registry.
- `src/study_agent/kernel/module.py`, `src/study_agent/state/registry.py`, `src/study_agent/state/projection.py`: module ownership and closure.
- `src/study_agent/ports/storage.py`: event-store protocol integration.
- `tests/contract/events/test_event_envelope.py`, `test_upcasters.py`, `test_kernel_module.py`, integration replay tests, and import-boundary tests.

## Acceptance Criteria

- [ ] Envelope contains validated identity, stream, time, correlation, causation, actor, schema, and payload fields.
- [ ] Unknown/malformed/unsupported/self-causating events fail closed; adjacent upcasters are pure, deterministic, and idempotent.
- [ ] Explicit module registration is immutable, ordered, and closed before runtime; collisions and late registration raise typed failures.
- [ ] Mixed-version replay is byte-identical and preserves lineage IDs and sequence.
- [ ] A host registers an opaque product event/reducer without a Harness import of any product package.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/events tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py`: envelope, upcasting, and replay pass.
- `uv run --python 3.13 --extra dev pytest -q tests/architecture/test_import_boundaries.py tests/architecture/test_capability_gateway_boundaries.py`: import and registration boundaries pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/domain src/study_agent/events src/study_agent/kernel src/study_agent/state src/study_agent/ports tests/contract/events`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Job lifecycle, workers, Decision Trace, telemetry, provider policy, storage implementation, product event meaning, and product files.
- Automatic unknown-schema migration, mutable history edits, and any second canonical stream.

## Removal Conditions

- Remove legacy `DomainEvent` adapters once all consumers use `EventEnvelope`, or keep them private behind tested upcasters only.
- No dual canonical stream or late mutable registry remains after acceptance.
