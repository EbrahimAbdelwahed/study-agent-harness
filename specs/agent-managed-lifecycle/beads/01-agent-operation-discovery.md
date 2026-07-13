# Task Bead: AML-01 agent operation discovery

Status: Complete
Priority: P1
Type: task
Depends On: none

## Worker Profile

reuse `implementer` for production code and `test-engineer` for independent
contract coverage

Rationale:

The public seam and invariants are already fixed by slice 01. Production and
test files can be assigned without overlapping writes; no new reusable
specialist profile is justified.

## Context

An automation client needs a stable offline description of the harness before
it can safely choose operations. The current argparse tree and dispatcher are
declared separately and StudyTool manifests are reachable only through runtime
tool composition.

## What To Do

- Add the closed CLI-local `CommandRegistration` registry.
- Make argparse construction, dispatch, and `agent-operations@1` serialization
  consume the same registrations.
- Expose the seven existing StudyTool manifests statically from their canonical
  definitions without changing their fingerprints.
- Add `describe` and `tool list|describe` operations that require no repository,
  credential, model, index, or network.
- Add exact-shape, parity, side-effect, and CLI-output contract tests.

## Likely Files / Packages

- `src/study_agent/cli/registry.py`: closed operation declarations and manifest.
- `src/study_agent/cli/main.py`: parser construction from registrations.
- `src/study_agent/cli/commands.py`: registered handler dispatch.
- `src/study_agent/tools/builtin.py`: static public manifest catalog.
- `tests/contract/cli/`: discovery and parity contract coverage.

## Acceptance Criteria

- [x] Empty-directory discovery succeeds with network denied and no filesystem mutation.
- [x] Parser, dispatcher, and discovery contain each operation exactly once.
- [x] `agent-operations@1` uses only the approved exact keys and enum values.
- [x] The exact seven StudyTool identities and fingerprints remain unchanged.
- [x] Output is deterministic and one machine-clean JSON document.
- [x] Existing unit, contract, architecture, lint, and type gates remain green.

## Verification

- `python -m pytest tests/contract/cli tests/contract/tools`: focused contracts pass.
- `python -m pytest`: full suite passes offline.
- `python -m ruff check .`: no lint regressions.
- `python -m mypy`: no type regressions.

## Out Of Scope

- Lazy/offline repository tool composition from slice 02.
- Course listing or explicit session start from slice 03.
- Operator-skill extraction from slice 04.
- Manifest reconciliation, generic command DSLs, plugins, MCP, or HTTP.

## Notes / Handoff

- Preserve the exact seven v0.1 StudyTool fingerprints.
- `operator_skill` remains `null` until slice 04.
- Review closed one descriptor defect: `model_setting` is a repeated CLI string
  in `NAME=JSON` form, not a raw JSON argv value.
