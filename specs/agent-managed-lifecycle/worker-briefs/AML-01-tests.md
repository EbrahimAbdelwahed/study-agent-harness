# Worker Brief: AML-01 tests

## Assignment

Add independent contract coverage for `AML-01` from
`specs/agent-managed-lifecycle/slices/01-agent-operation-discovery.md`.

## Read First

- `specs/agent-managed-lifecycle/slices/01-agent-operation-discovery.md`
- `specs/agent-managed-lifecycle/beads/01-agent-operation-discovery.md`
- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/main.py`
- `src/study_agent/tools/builtin.py`
- `tests/contract/tools/test_public_tool_contract.py`
- `tests/contract/cli/test_reference_cli_process_contract.py`

## Scope

You may change:

- `tests/unit/cli/test_main.py`
- `tests/contract/cli/test_reference_cli_process_contract.py`
- `tests/contract/cli/test_agent_operation_discovery.py`

Do not change:

- `src/`
- any other tests, specs, docs, packaging, or version files
- any file outside `study-agent-harness`

## Requirements

- Test only observable public behavior and closed contract invariants.
- Update the legacy top-level help assertion only for the three additive commands.
- Assert exact root, command, argument, and StudyTool-entry shapes and closed enums.
- Assert deterministic stable sorting and exact seven existing fingerprints.
- Assert all parser leaf commands and discovery descriptors have one-to-one parity.
- Prove `describe` and `tool list|describe` succeed from an empty directory with
  no filesystem mutation, no credential access, and no socket use.
- Assert one JSON stdout document and safe unknown-tool failure.
- Do not pin handler implementation details or mock internal call chains.

## Verification

Run:

```bash
python -m pytest tests/unit/cli/test_main.py tests/contract/cli tests/contract/tools
python -m ruff check tests/unit/cli/test_main.py tests/contract/cli
python -m mypy
```

## Report Back

Return:

- files changed;
- behaviors pinned;
- proof the new tests fail appropriately when a contract field is removed;
- exact verification results;
- unresolved findings.
