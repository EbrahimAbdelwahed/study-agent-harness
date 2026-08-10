# Task Bead: PF-08 Async-first runtime

Status: Open
Priority: P1
Type: task
Depends On: PF-01, PF-02, PF-03, PF-04, PF-05, PF-06, PF-07

## Outcome

An embedding Host constructs one provider-neutral runtime by explicit
dependency injection and invokes capability, source, artifact, assessment,
and recall services asynchronously or through a sync wrapper over the same
state and event stream.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-08 dependency bundle, async runtime methods, sync delegation, lifecycle, validation, and cancellation criteria in `specs/package-foundation/slices/PF-08-runtime.md`.
- README explicit composition, no global state, and Host/planner ownership invariants.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-08-runtime.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `local-composition-worker`

Rationale:

The task is explicit host composition over existing ports, bounded orchestration,
offline scripted adapters, and lifecycle checks, matching the composition profile.

## Context

Later distribution checks require one embeddable runtime rather than hidden
service locators or a second synchronous state machine. Runtime validation
precedes adapters; Hosts retain planning, policy, credentials, and process
lifecycle.

## Invariants

- Frozen `RuntimeDependencies` requires principal, repository, storage, clock, ID factory, model adapter, and policy; missing values fail at construction.
- `AsyncStudyAgentRuntime` is the only execution implementation; sync methods delegate to that exact instance and own no state.
- Runtime validates schema, authority, stale reads, citations, provenance, and outputs before adapters; canonical events append only through the shared store.
- Cancellation is cooperative before commit; committed events remain; adapter/provider errors map through PF-02 and never expose credentials or raw output.
- No global locator, singleton, environment auto-wiring, planner, Job queue, browser/auth session, product import, or process-global current runtime exists.

## What To Do

- Implement dependency bundle validation, `create_runtime`, `AsyncStudyAgentRuntime` methods, typed DTOs, and close behavior.
- Implement `SyncStudyAgentRuntime` delegation and running-loop guard.
- Compose offline scripted capability/source/artifact/assessment/recall calls with fake clock, IDs, storage, policy, and model adapter.
- Add tests for equal async/sync results, one append, missing dependencies, translation, cancellation, close idempotency, and no global state.

## Likely Allowed Files / Packages

- `src/study_agent/api/runtime.py`, `src/study_agent/application/runtime.py`, `application/harness.py`, `runtime.py`.
- `src/study_agent/hosts/**`, `src/study_agent/ports/model.py`, `ports/storage.py`, `ports/clock.py`, and narrow runtime exports.
- `tests/contract/runtime/**`, host unit/integration tests named by PF-08, and runtime architecture tests.

## Acceptance Criteria

- [ ] Explicit dependency injection constructs a typed runtime and rejects missing required ports with validation failure.
- [ ] Async public methods cover capability discovery, snapshot read, start/resume, artifact decision, assessment observation, recall review, and close.
- [ ] Sync facade calls the same async object, returns identical serialized results, and rejects calls from an active event loop with a clear error.
- [ ] Offline invocation proves one event stream, typed validation/authority/citation/provenance, safe adapter errors, cancellation, and idempotent close.
- [ ] No hidden global state, planner behavior, provider auto-discovery, raw adapter type, Cardine import, or duplicate persistence path remains.

## Verification

- `uv run --python 3.13 --extra dev pytest -q tests/contract/runtime tests/unit/hosts tests/unit/hosts/test_tutor_host_runner.py`: runtime contracts pass.
- `uv run --python 3.13 --extra dev pytest -q tests/integration/test_offline_tool_composition.py tests/integration/test_tutor_host_runner.py tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_host_file_snapshots.py`: offline integration passes.
- `uv run --python 3.13 --extra dev pytest -q tests/architecture/test_tutor_host_boundaries.py tests/architecture/test_import_boundaries.py`: boundaries pass.
- `uv run --python 3.13 --extra dev ruff check src/study_agent/api/runtime.py src/study_agent/application src/study_agent/hosts src/study_agent/ports tests/contract/runtime`: lint passes.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Autonomous planner, Job/lease/retry queue, worker scheduler, Decision Trace, UI, browser/auth session, hosted service, telemetry, and product composition.

## Removal Conditions

- Remove legacy composition helpers that create hidden globals or a second sync state machine once all callers use `create_runtime` and the two facade classes.

