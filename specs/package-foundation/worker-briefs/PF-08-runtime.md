# Worker Brief: PF-08

## Assignment

Implement `PF-08` from `specs/package-foundation/slices/PF-08-runtime.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01 through PF-08 slices, and `specs/package-foundation/beads/PF-08-runtime.md`
- existing host composition, runtime, capability, source, artifact, assessment, recall, and port modules/tests

## Scope

You may change:

- `src/study_agent/api/runtime.py`, `src/study_agent/application/runtime.py`, `application/harness.py`, `runtime.py`
- `src/study_agent/hosts/**`, `src/study_agent/ports/model.py`, `ports/storage.py`, `ports/clock.py`, and narrow runtime exports
- runtime contract, host unit/integration, and architecture tests named by PF-08

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, domain owners from PF-02 through PF-07 except narrow port wiring, planner/policy semantics, CLI/UI, hosted service, telemetry, product modules, or dependencies

## Invariants and Requirements

- Frozen `RuntimeDependencies` requires principal, repository, storage, clock, ID factory, model adapter, and policy; missing values fail at construction.
- `AsyncStudyAgentRuntime` is the only execution implementation; sync wrapper delegates to that instance and owns no state.
- Runtime validates schema, authority, stale reads, citations, provenance, and outputs before adapters and appends canonical events only through shared storage.
- Cancellation is cooperative before commit, committed events remain, adapter failures map to PF-02, and provider output/credentials never enter public DTOs.
- No global locator, singleton, environment auto-wiring, planner, Job queue, browser/auth session, product import, or duplicate persistence path exists.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/runtime tests/unit/hosts tests/unit/hosts/test_tutor_host_runner.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_offline_tool_composition.py tests/integration/test_tutor_host_runner.py tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_host_file_snapshots.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_tutor_host_boundaries.py tests/architecture/test_import_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/api/runtime.py src/study_agent/application src/study_agent/hosts src/study_agent/ports tests/contract/runtime
git diff --check
```

## Report Back

Return files changed, dependency injection/async/sync/offline behavior, exact
verification, profile constraints followed, unresolved questions, and follow-up beads.
