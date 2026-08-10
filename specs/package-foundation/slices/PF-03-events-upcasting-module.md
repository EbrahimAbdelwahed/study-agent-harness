# PF-03 — Events, upcasting, and module

Status: Complete

## Outcome

One versioned event envelope and one immutable module-registration seam make
canonical state append-only, replayable, and extensible by a downstream host.
Older supported event payloads upcast deterministically; malformed, unknown,
colliding, or late registrations fail closed.

## Non-goals

- No Job lifecycle, worker orchestration, Decision Trace, telemetry, or queue.
- No Cardine-owned event semantics inside Harness; product events enter only as
  explicitly registered `KernelModule` contributions.
- No mutable event edits, event deletion, projection-as-authority, or automatic
  migration from arbitrary unknown schemas.

## Exact contracts

- `EventEnvelope` is frozen and versioned. It contains `event_id`, `event_type`,
  `schema_version`, `stream_id`, `stream_sequence`, `occurred_at`,
  `correlation_id`, optional `causation_id`, trusted `actor`, and validated
  JSON `payload`. IDs and timestamps are opaque typed values and timestamps are
  timezone-aware.
- Event type names are namespaced lowercase strings. Schema versions are
  positive integers. Payloads are deep-frozen JSON values with no NaN,
  infinities, bytes, executable objects, or provider objects.
- Append validates sequence, actor, schema, and payload before storage. The
  append-only stream is canonical; projections, snapshots, indexes, caches,
  and operational runs are rebuildable and never write canonical facts.
- `EventUpcasterRegistry` maps `(event_type, old_schema_version)` to one
  deterministic pure upcaster. An upcaster may only produce the next supported
  schema and must be idempotent for the same input. Unknown types, unsupported
  versions, ambiguous paths, and malformed payloads raise `ValidationFailure`.
- `KernelModule` is an immutable value containing module ID/version, event
  schemas, reducer/projection registrations, service ports, and capability
  registrations. Registration is explicit at composition time, sorted by
  namespace, and closed before runtime start.
- Duplicate event schema names, reducer/projection owners, service names, or
  capability identities raise `ConflictFailure`. Unknown event schemas and
  registration after closure raise `ValidationFailure`. Harness never imports
  Cardine to discover product modules.
- A host may register product reducers/projections through `KernelModule`; they
  share the per-course event store and sequence with Harness-owned events.
  Decision Trace remains a separate future-runtime stream and is not a domain
  projection input.
- Replay from the same event bytes, upcaster versions, and reducer versions
  produces byte-identical projection output. Event IDs, correlation IDs, and
  causation IDs are preserved through upcasting.

## Probable files

- `src/study_agent/api/events.py` or `src/study_agent/domain/events.py` —
  public envelope and schema codec.
- `src/study_agent/events/upcasting.py` — deterministic registry and adapters.
- `src/study_agent/kernel/module.py` — immutable `KernelModule` and closure.
- `src/study_agent/state/registry.py` and `src/study_agent/state/projection.py`
  — reducer/projection ownership checks.
- `src/study_agent/ports/storage.py` — event-store protocol updates.
- `tests/contract/events/test_event_envelope.py`,
  `tests/contract/events/test_upcasters.py`, and
  `tests/contract/events/test_kernel_module.py`.
- `tests/integration/test_event_state_kernel.py` and
  `tests/architecture/test_import_boundaries.py`.

## Dependencies

PF-01 supplies public exports and PF-02 supplies safe failures and authority.
PF-04 consumes the envelope for event-store and replay contract tests. PF-06
consumes module closure for capability registration.

## Removal conditions

Any temporary adapter from the legacy `DomainEvent` shape must be removed once
all event-store consumers use `EventEnvelope`, or remain private and covered by
an explicit upcaster test. No dual canonical stream may survive acceptance.

## Review surface

Review envelope field names, canonical JSON rules, sequence ownership,
upcaster purity, and module collision/closure behavior. Replay a mixed old/new
fixture and inspect that projections are equal and no model/provider import is
needed.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/events tests/integration/test_event_state_kernel.py tests/integration/test_source_projection_replay.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_import_boundaries.py tests/architecture/test_capability_gateway_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/domain src/study_agent/events src/study_agent/kernel src/study_agent/state tests/contract/events
git diff --check
```

Fixtures must cover sequence conflicts, self-causation, malformed JSON,
unsupported versions, deterministic old-to-current replay, collision, late
registration, and an authorized product module with an opaque event type.

## Risks

- A reducer or projection can become a hidden authority. Enforce one owner and
  rebuild it only from the append-only stream.
- Permissive upcasting can silently reinterpret history. Permit only declared
  adjacent versions and fail closed on unknown fields or types.
- A mutable registry can change replay semantics mid-run. Freeze modules and
  reject late registration after runtime construction.

## Definition of done

- Event envelope, upcaster registry, and `KernelModule` are public through the
  curated facade with typed codecs.
- Existing v1 event fixtures replay unchanged and new schemas replay
  deterministically.
- Module collisions, unknown schemas, late registration, and unsafe payloads
  fail with typed public errors.
- Product modules can register without a Harness-to-Cardine import.
- Focused contract, integration, architecture, lint, and diff checks pass.
