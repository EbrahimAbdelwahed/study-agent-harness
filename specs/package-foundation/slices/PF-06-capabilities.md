# PF-06 — Capabilities

## Outcome

Hosts explicitly register trusted capabilities through immutable, namespaced,
versioned manifests and permissioned bindings. Discovery is deterministic;
dispatch validates input, authority, provenance, idempotency, and output before
returning a completed, suspended, cancelled, stale, or failed outcome.

## Non-goals

- No import-time, entry-point, package-scan, or untrusted plugin discovery.
- No generic Job queue, worker pool, web evidence, sealed verification, or
  Decision Trace; those are future runtime slices.
- No host planner inside Harness. Cardine or another Host selects the bounded
  capability; Harness validates and executes it.

## Exact contracts

- `CapabilityId` is a namespaced, lowercase opaque identifier. A
  `CapabilityManifest` is frozen and contains ID, semantic version, input and
  output JSON schemas, required authority grants, supported suspension flag,
  implementation contract version, and deterministic fingerprint.
- Namespaces and identities are unique within one immutable
  `CapabilityRegistry`. Duplicate ID/version, schema collision, unknown grant,
  late registration, or registration from an untrusted import path raises a
  typed public failure.
- A host constructs a `KernelModule` and passes it to explicit composition.
  Registry construction is the only discovery path; the harness never scans
  Python entry points or imports Cardine to find capabilities.
- `CapabilityBinding` associates one manifest with one provider-neutral
  executor port and validator set. Providers/models may implement transport,
  but they cannot alter the manifest, authority, canonical event type, or
  output acceptance policy.
- `CapabilityRequest` contains manifest identity, frozen JSON input,
  `AuthorityContext`, correlation ID, expected stream high-water, and
  idempotency key. Required grants are checked before execution; `MODEL` is
  rejected for durable effects.
- `CapabilityOutcome` is a closed tagged union: `COMPLETED`, `SUSPENDED`,
  `CANCELLED`, `STALE`, or `FAILED`. Completed output is schema-validated and
  provenance-pinned. Suspension carries an opaque continuation bound to
  capability/version, authority, input fingerprint, and checkpoint.
- An exact retry with the same idempotency identity returns the prior outcome;
  changed input, authority, manifest, or checkpoint returns `ConflictFailure`
  or `StaleFailure` without a duplicate canonical event. Cancellation is safe
  before commit and cannot erase a committed event.
- Read-only tools remain callable through a host-owned tool surface. New
  durable effects route through permissioned capabilities and proposals; a
  capability cannot silently accept its own generated artifact.

## Probable files

- `src/study_agent/api/capabilities.py` — public manifest, registry, binding,
  request, continuation, and outcome exports.
- `src/study_agent/capabilities/contracts.py`, `registry.py`, `bindings.py`,
  `gateway.py`, and `dispatch.py` — implementation and validation seam.
- `src/study_agent/kernel/module.py` — explicit module contribution.
- `src/study_agent/ports/worker.py` and `src/study_agent/ports/model.py` —
  provider-neutral executor/transport ports.
- `tests/contract/capabilities/test_capability_registry_contract.py`,
  `tests/contract/capabilities/test_capability_gateway_contract.py`, and
  `tests/contract/capabilities/test_capability_manifest_contract.py`.
- `tests/integration/test_capability_gateway_lifecycle.py`,
  `tests/integration/test_builtin_capability_gateway.py`, and
  `tests/architecture/test_capability_gateway_boundaries.py`.

## Dependencies

PF-01 supplies the facade, PF-02 supplies authority/failures, PF-03 supplies
module and event registration, and PF-04 supplies operational storage/CAS.
PF-07 uses capability dispatch for generic artifact and assessment effects.

## Removal conditions

Remove legacy registry aliases and any import-time registration path before
acceptance. A temporary adapter from the current playbook gateway may remain
only until every consumer uses the manifest/binding contract and has a focused
removal test.

## Review surface

Inspect manifest fingerprint inputs, namespace/version uniqueness, explicit
composition, model restrictions, continuation binding, and retry identity.
Probe unknown capability, missing grant, changed input, stale dependency,
duplicate registration, and provider protocol errors.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/capabilities tests/unit/capabilities
uv run --python 3.13 --extra dev pytest -q tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_builtin_capability_gateway.py tests/integration/test_capability_run_recovery.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_capability_gateway_boundaries.py tests/architecture/test_tool_registry_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/capabilities src/study_agent/kernel src/study_agent/ports tests/contract/capabilities
git diff --check
```

Fixtures must cover deterministic discovery, schema rejection, authority
failure, equal-key retry, changed-input conflict, continuation mismatch,
cooperative cancellation, validated completion, and no import-time side effect.

## Risks

- Entry-point discovery can make untrusted code authoritative. Keep registry
  construction explicit and immutable.
- Provider output can bypass validators through a direct executor call. Bind
  validators and authority at the gateway, not in provider adapters.
- A continuation can outlive its grants or source reads. Fingerprint all
  authority, input, manifest, checkpoint, and read dependencies.

## Definition of done

- Trusted manifests, bindings, registry, gateway, and outcomes are exposed via
  the capability subfacade with no provider types.
- Explicit registration is the only discovery path and rejects collisions.
- Model authority cannot commit durable effects or approvals.
- Retry, suspension, stale input, cancellation, and output validation are
  contract-tested and replay-safe.
- Focused contract, integration, architecture, lint, and diff checks pass.
