# Worker Brief: PF-06

## Assignment

Implement `PF-06` from `specs/package-foundation/slices/PF-06-capabilities.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01 through PF-06 slices, and `specs/package-foundation/beads/PF-06-capabilities.md`
- existing capability gateway/registry, worker/model ports, KernelModule, and capability tests

## Scope

You may change:

- `src/study_agent/api/capabilities.py`
- `src/study_agent/capabilities/contracts.py`, `registry.py`, `bindings.py`, `gateway.py`, `dispatch.py`
- `src/study_agent/kernel/module.py`, `src/study_agent/ports/worker.py`, `ports/model.py`
- capability contract/unit/integration/architecture tests named by PF-06

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, artifact/assessment/recall owners, product files, planner policy, CLI/UI, import-discovery policy, or dependencies

## Invariants and Requirements

- Manifests are frozen namespaced lowercase IDs with semantic version, input/output JSON schemas, grants, suspension flag, implementation version, and deterministic fingerprint.
- Explicit KernelModule registry construction is the only discovery path; reject duplicates, unknown grants/schemas, untrusted registration, and late closure.
- Gateway checks grants and authority before executor/provider access; MODEL cannot commit durable effects or approve artifacts.
- Outcomes are exactly completed, suspended, cancelled, stale, or failed; continuations bind capability/version, authority, input, checkpoint, and dependencies.
- Retry identity, output validation, cancellation, and stale handling preserve one canonical event and PF-02 safe failures.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/capabilities tests/unit/capabilities
uv run --python 3.13 --extra dev pytest -q tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_builtin_capability_gateway.py tests/integration/test_capability_run_recovery.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_capability_gateway_boundaries.py tests/architecture/test_tool_registry_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/capabilities src/study_agent/kernel src/study_agent/ports tests/contract/capabilities
git diff --check
```

## Report Back

Return files changed, manifest/registry/gateway behavior, exact verification,
profile constraints followed, unresolved questions, and follow-up beads.
