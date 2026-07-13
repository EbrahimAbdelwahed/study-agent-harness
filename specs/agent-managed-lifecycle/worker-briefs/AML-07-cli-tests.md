# Worker Brief: AML-07 CLI migration and tests

## Assignment

Move procedural source ingestion to the shared snapshot adapter, delete the
private reader, and independently pin the complete contract.

## Production Scope

- `src/study_agent/cli/commands.py`

## Test Scope

- focused source-reader cases in `tests/unit/cli/test_commands.py`
- `tests/contract/ports/test_source_input_contract.py`
- `tests/contract/filesystem/test_source_input.py`
- focused reference CLI integration and lifecycle architecture guards

## Invariants

- Relative procedural sources remain repository-anchored; explicit absolute
  paths are trusted-host inputs only when inside that root.
- Source ID/title/filename behavior remains compatible.
- No `_read_source`, second filesystem reader or lifecycle-specific wrapper
  remains.
- Exact seven StudyTools and event-sourced state behavior remain unchanged.

## Gates

- Focused and full pytest
- Ruff and strict mypy
- `git diff --check`
- semantic and security review
