# Task Bead: AML-02 offline tool composition

Status: Complete
Priority: P1
Type: task
Depends On: AML-01

## Worker Profile

reuse `implementer`

Rationale:

The contract is fixed and the work is a bounded dependency-construction change
inside the existing tool and local-repository composition roots.

## Context

`LocalRepository.study_tools()` currently rebuilds retrieval and constructs a
model-backed grounding service before a caller can even enumerate manifests.
This violates the offline-default and makes six non-model tools depend on model
configuration.

## What To Do

- Make grounding-service construction lazy at `GroundingAskTool` invocation.
- Keep the exact seven registry and manifest contracts unchanged.
- Translate missing technical model configuration into the existing portable
  application/tool error without leaking CLI exceptions.
- Ensure registry construction neither rebuilds retrieval nor creates run/event
  state.
- Add offline and missing-model regression coverage.

## Likely Files / Packages

- `src/study_agent/tools/builtin.py`
- `src/study_agent/tools/registry.py`
- `src/study_agent/cli/repository.py`
- `tests/integration/test_offline_tool_composition.py`

## Acceptance Criteria

- [x] Offline `study_tools()` returns the exact seven manifests.
- [x] Six applicable non-grounding tools remain invokable offline.
- [x] Only `grounding.ask` resolves the model provider.
- [x] Missing-model ask returns `incompatible_runtime` without run/event writes.
- [x] Registry access does not rebuild retrieval.
- [x] Fingerprints and scripted-model parity remain unchanged.

## Verification

- `python -m pytest tests/integration/test_offline_tool_composition.py tests/contract/tools`
- `python -m pytest`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`

## Out Of Scope

- CLI lifecycle additions from AML-03.
- Provider/model branching, prompt changes, or new StudyTools.

## Notes / Handoff

- The lazy boundary is dependency construction only; grounding behavior remains
  in the existing application service, skill, playbook, and prompt.
- Review replaced callable inference with a nominal, successfully memoized
  provider and added socket-denial and reverse-import guards.
