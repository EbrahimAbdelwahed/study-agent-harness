# Task Bead: PF-06 Capabilities

Status: Open
Priority: P1
Type: task
Depends On: PF-01, PF-02, PF-03, PF-04

## Outcome

Hosts explicitly register immutable, namespaced capability manifests and
permissioned bindings. Dispatch validates authority, provenance, idempotency,
suspension, cancellation, stale inputs, and outputs without plugin scanning.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-06 manifest, registry, binding, gateway, outcome, and discovery criteria in `specs/package-foundation/slices/PF-06-capabilities.md`.
- README explicit composition, MODEL restrictions, and provider-neutral boundary invariants.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-06-capabilities.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `typed-tool-harness-worker`

Rationale:

Capability manifests, schemas, trusted registration, validation, and effect
gates have the same shape as the existing typed-tool harness profile.

## Context

Hosts need a deterministic gateway for bounded capabilities while retaining
planner and policy ownership. Registry construction is explicit and immutable;
provider output is untrusted until gateway validators accept it.

## Invariants

- Capability IDs are lowercase namespaced opaque values; manifests are frozen, versioned, schema-bound, permissioned, and fingerprinted.
- Registry construction through a `KernelModule` is the only discovery path; no import-time, entry-point, package-scan, or product import occurs.
- Required grants and authority are checked before executor/provider access; MODEL cannot commit durable effects or approvals.
- Outcomes are exactly completed, suspended, cancelled, stale, or failed; suspension binds capability/version, authority, input, checkpoint, and dependencies.
- Equal identity retries converge; changed input/authority/checkpoint conflicts or stales without duplicate canonical events; output is validated before return.

## What To Do

- Implement manifests, schema fingerprints, explicit registry closure, bindings, and executor/validator ports.
- Implement gateway request validation, authority checks, outcome union, continuation binding, cancellation, and safe exception mapping.
- Integrate KernelModule capability registration and remove import-time registration paths.
- Add deterministic registry, schema, grant, retry, continuation, stale, cancellation, output, and side-effect tests.

## Likely Allowed Files / Packages

- `src/study_agent/api/capabilities.py`, `src/study_agent/capabilities/contracts.py`, `registry.py`, `bindings.py`, `gateway.py`, `dispatch.py`.
- `src/study_agent/kernel/module.py`, `src/study_agent/ports/worker.py`, `src/study_agent/ports/model.py`.
- `tests/contract/capabilities/**`, `tests/unit/capabilities/**`, named integration and architecture tests.

## Acceptance Criteria

- [ ] Manifests, registry, bindings, requests, continuations, and outcomes are typed and importable without provider types.
- [ ] Explicit trusted registration is deterministic, immutable, namespaced, permissioned, and rejects duplicate/unknown/late entries.
- [ ] Missing grants, MODEL durable effects, malformed input, provider failures, stale dependencies, and invalid output fail closed before side effects.
- [ ] Exact retries return prior outcomes; changed identity conflicts; suspension/resume and cancellation preserve canonical event semantics.
- [ ] No import-time side effect, entry-point scan, product import, or self-acceptance path remains.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/capabilities tests/unit/capabilities`: contracts pass.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_builtin_capability_gateway.py tests/integration/test_capability_run_recovery.py`: lifecycle tests pass.
- `uv run --python 3.13 --extra dev pytest -q tests/architecture/test_capability_gateway_boundaries.py tests/architecture/test_tool_registry_boundaries.py`: boundaries pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/capabilities src/study_agent/kernel src/study_agent/ports tests/contract/capabilities`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Job queues, workers, web evidence, sealed verification, Decision Trace, host planner, product policy, import scanning, and new dependencies.

## Removal Conditions

- Remove legacy registry aliases and import-time registration after all consumers use manifest/binding contracts and focused removal tests pass.

