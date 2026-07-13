# Worker Brief: AML-02 production

## Assignment

Implement `AML-02` from
`specs/agent-managed-lifecycle/slices/02-offline-tool-composition.md`.

## Read First

- `specs/agent-managed-lifecycle/README.md`
- `specs/agent-managed-lifecycle/slices/02-offline-tool-composition.md`
- `specs/agent-managed-lifecycle/beads/02-offline-tool-composition.md`
- `src/study_agent/tools/builtin.py`
- `src/study_agent/tools/registry.py`
- `src/study_agent/cli/repository.py`

## Scope

You may change:

- `src/study_agent/tools/builtin.py`
- `src/study_agent/tools/registry.py`
- `src/study_agent/cli/repository.py`
- `tests/integration/test_offline_tool_composition.py`

Do not change:

- CLI registry/main/commands, existing tests, specs/docs, versions, packaging
- any file outside `study-agent-harness`

## Requirements

- Preserve the exact seven manifests/fingerprints and existing eager-service
  constructor compatibility where tests/embedders already use it.
- Resolve grounding lazily only on `grounding.ask` invocation.
- Do not import `study_agent.cli` from tools/application/domain/ports.
- Map absent model configuration to
  `GroundingAskError(INCOMPATIBLE_RUNTIME)` at the composition boundary.
- Merely constructing/enumerating a registry must not rebuild retrieval, touch
  run/event state, enumerate credentials, or create a model.
- No provider/model-name branches and no behavior/prompt duplication.

## Verification

Run the focused integration test, tool contracts, Ruff, and mypy described in
the bead. Do not commit or push.

## Report Back

Return files, behavior, red/green regression evidence, exact gates, and findings.
