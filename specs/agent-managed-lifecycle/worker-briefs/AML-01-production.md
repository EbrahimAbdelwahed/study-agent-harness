# Worker Brief: AML-01 production

## Assignment

Implement production code for `AML-01` from
`specs/agent-managed-lifecycle/slices/01-agent-operation-discovery.md`.

## Read First

- `specs/agent-managed-lifecycle/README.md`
- `specs/agent-managed-lifecycle/slices/01-agent-operation-discovery.md`
- `specs/agent-managed-lifecycle/beads/01-agent-operation-discovery.md`
- `src/study_agent/cli/main.py`
- `src/study_agent/cli/commands.py`
- `src/study_agent/tools/builtin.py`

## Scope

You may change:

- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/main.py`
- `src/study_agent/cli/commands.py`
- `src/study_agent/tools/builtin.py`
- `src/study_agent/tools/__init__.py`

Do not change:

- `tests/`
- `specs/`, `docs/`, packaging, or version files
- any file outside `study-agent-harness`

## Requirements

- One closed CLI-local registration is the owner for parser callback, handler,
  and serializable metadata for every leaf command.
- Do not build a generic command DSL, plugin surface, or runtime-loaded registry.
- Discovery must not open a repository or resolve credentials/models.
- Static tool discovery must derive from the existing canonical manifest
  definitions and preserve all seven fingerprints exactly.
- Keep current CLI behavior and JSON envelopes compatible.

## Verification

Run:

```bash
python -m pytest tests/unit/cli tests/contract/cli tests/contract/tools
python -m ruff check src/study_agent/cli src/study_agent/tools
python -m mypy
```

## Report Back

Return:

- files changed;
- behavior implemented;
- verification results;
- unresolved questions;
- follow-up beads needed.
