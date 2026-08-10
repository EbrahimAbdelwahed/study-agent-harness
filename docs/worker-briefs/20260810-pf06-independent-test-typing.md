# Worker Brief: PF-06 independent test typing

## Assignment

Implement Bead `study-agent-harness-integration-1u7.1.1` as a tests-only strict
typing correction.

## Allowed files

- `tests/contract/test_public_sources_facade.py`
- `tests/architecture/test_tool_registry_boundaries.py`

## Forbidden files and invariants

- No production, gateway, public contract, spec, metadata, or lock changes.
- Use validated type narrowing and explicit collection annotations. Do not add
  `Any`, blanket casts, ignores, or weaken assertions.
- Do not delegate, merge, close beads, delete worktrees, or release another
  reservation. Commit only allowed files and report in the bead thread.

## Acceptance and verification

```text
uv run --frozen --offline --python 3.13 --extra dev pytest -q tests/contract/test_public_sources_facade.py tests/architecture/test_tool_registry_boundaries.py
uv run --frozen --offline --python 3.13 --extra dev ruff check tests/contract/test_public_sources_facade.py tests/architecture/test_tool_registry_boundaries.py
uv run --frozen --offline --python 3.13 --extra dev mypy --strict tests/contract/test_public_sources_facade.py tests/architecture/test_tool_registry_boundaries.py
git diff --check
```

Report files, exact results, SHA, and blockers. Leave the bead open.
