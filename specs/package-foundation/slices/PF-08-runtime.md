# PF-08 — Async-first runtime

## Outcome

An embedding Host constructs one provider-neutral runtime by dependency
injection and can invoke the same capability, source, artifact, assessment,
and recall services asynchronously or through a sync convenience facade. The
runtime owns bounded orchestration and validation, while the Host owns
planning, policy, adapters, and process lifecycle.

## Non-goals

- No autonomous planner, unbounded agent loop, Job/lease/retry queue, worker
  scheduler, or Decision Trace stream.
- No hidden global configuration, singleton service locator, environment-based
  auto-wiring, or implicit provider selection.
- No UI, browser/auth session, hosted service, remote telemetry, or Cardine
  composition import.

## Exact contracts

- `RuntimeDependencies` is frozen and requires explicit `principal`,
  `repository`, `storage`, `clock`, `id_factory`, `model_adapter`, and
  `policy`. Optional adapters are explicit fields or capability bindings;
  missing required dependencies fail at construction with `ValidationFailure`.
- `AsyncStudyAgentRuntime` is the only execution implementation. Its public
  methods are asynchronous and typed: `discover_capabilities()`,
  `read_snapshot()`, `start_capability()`, `resume_capability()`,
  `record_artifact_decision()`, `record_assessment_observation()`,
  `review_recall()`, and `close()`.
- Each method accepts an `AuthorityContext`, correlation identity, and the
  relevant idempotency/expected-sequence inputs. It returns a typed facade DTO
  or closed `CapabilityOutcome`; it never exposes provider, SQLite, filesystem,
  or internal playbook types.
- The runtime performs schema, authority, stale-read, citation, provenance,
  and output validation before invoking an adapter. It commits canonical events
  only through the shared event store and returns a replayable result.
- `SyncStudyAgentRuntime` is a convenience wrapper over an existing
  `AsyncStudyAgentRuntime` instance. It calls the same coroutine methods and
  owns no state or alternate persistence path. Calls from an already-running
  event loop raise a clear `RuntimeError` instructing the caller to use async.
- Runtime construction is explicit (`create_runtime(dependencies, modules)`)
  and closes all host-supplied resources through their declared ports. No
  import-time side effect or process-global current runtime exists.
- Cancellation is cooperative at declared suspension/commit checkpoints;
  committed events remain committed. Adapter failure maps through PF-02 and
  does not expose raw model output or credentials.
- A model adapter is transport-only. Prompts and provider settings remain
  outside canonical event DTOs; any generated content enters through proposal
  or observation contracts from PF-07.

## Probable files

- `src/study_agent/api/runtime.py` — public dependency/runtime DTOs.
- `src/study_agent/application/runtime.py` or `src/study_agent/runtime.py` —
  async implementation and sync wrapper.
- `src/study_agent/application/harness.py`, `src/study_agent/hosts/runner.py`,
  and `src/study_agent/hosts/contracts.py` — composition migration.
- `src/study_agent/ports/model.py`, `src/study_agent/ports/storage.py`, and
  `src/study_agent/ports/clock.py` — injected boundary protocols.
- `tests/contract/runtime/test_async_runtime_contract.py` and
  `tests/contract/runtime/test_sync_runtime_facade.py`.
- `tests/integration/test_offline_tool_composition.py`,
  `tests/integration/test_tutor_host_runner.py`,
  `tests/integration/test_capability_gateway_lifecycle.py`, and
  `tests/architecture/test_tutor_host_boundaries.py`.

## Dependencies

PF-01 supplies the runtime subfacade, PF-02 supplies errors/authority, PF-03
and PF-04 supply events/storage, PF-05 supplies citations, PF-06 supplies
capabilities, and PF-07 supplies domain service contracts. PF-09 consumes the
runtime import boundary.

## Removal conditions

Remove any legacy composition helper that creates hidden globals or a second
sync state machine after all callers use `create_runtime` and the two facade
classes. Keep a private adapter only while its named caller migrates and its
equivalence test remains green.

## Review surface

Review the dependency bundle, runtime method signatures, async/sync delegation
proof, lifecycle close behavior, cancellation checkpoints, and absence of
provider or product types. Use a fake clock, deterministic IDs, scripted model,
and in-memory storage for a complete offline invocation.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/runtime tests/unit/hosts tests/unit/hosts/test_tutor_host_runner.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_offline_tool_composition.py tests/integration/test_tutor_host_runner.py tests/integration/test_capability_gateway_lifecycle.py tests/integration/test_host_file_snapshots.py
uv run --python 3.13 --extra dev pytest -q tests/architecture/test_tutor_host_boundaries.py tests/architecture/test_import_boundaries.py
uv run --python 3.13 --extra dev ruff check src/study_agent/api/runtime.py src/study_agent/application src/study_agent/hosts src/study_agent/ports tests/contract/runtime
git diff --check
```

The tests must prove identical async and sync results, no duplicate event
append, missing-dependency failure, model/provider exception translation,
cooperative cancellation, close idempotency, and no global runtime state.

## Risks

- A sync wrapper can accidentally fork state or invoke a second reducer. Keep a
  reference to the async runtime and assert one event stream in tests.
- Host policy can leak into kernel behavior. Accept policy as a narrow port and
  keep planner decisions outside the runtime.
- Async adapter exceptions can escape in cancellation paths. Exercise failure,
  cancellation, and close branches with typed error assertions.

## Definition of done

- Host dependency injection and async runtime contracts are stable and public.
- Sync convenience delegates to the same async object with no duplicated state.
- Offline scripted composition covers capability, source, artifact, assessment,
  and recall calls through typed DTOs.
- No global locator, provider auto-discovery, Cardine import, or raw adapter
  exception remains at the facade.
- Focused contract, integration, architecture, lint, and diff checks pass.
