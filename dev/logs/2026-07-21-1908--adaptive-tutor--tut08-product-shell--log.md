# Log: TUT-08 Build Week product shell

Date: 2026-07-21 19:08
Area: adaptive-tutor / product shell

## Summary

Added a terminal-first, conversation-first product-shell consumer over the
public snapshot, capability discovery, and host-result contracts. The shell
accepts bounded free-form learner text immediately, renders material/context/
conversation evidence, exposes optional due review, and maps suspended, stale,
degraded, and recovered host states without owning canonical state.

## Files Changed

- `src/study_agent/demo/product_shell.py`: reusable shell view, statuses,
  optional due-review seam, deterministic renderer, and offline command.
- `pyproject.toml`: `study-agent-shell` entry point.
- `tests/unit/demo/test_product_shell.py`: focused shell contract checks.
- `tests/integration/demo/TUT08/test_offline_shell.py`: one-command offline
  journey check.
- `docs/product-shell.md`: sample/eval/video script and state contract.
- `specs/adaptive-tutor/beads/TUT-08-build-week-product-shell.md`: status
  updated from obsolete TUT-06 block to in-progress terminal tracer.

## Verification

- `ruff check src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08`: passed.
- `python3 -m compileall -q src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08`: passed.
- `PYTHONPATH=src python3 -m study_agent.demo.product_shell --json`: passed;
  recovered trace, material checksum, evidence sequence, capability parity,
  and optional-recall fallback were emitted.
- `git diff --check`: passed.
- Pytest, mypy, and wheel commands were attempted but this isolated worktree
  has no `.venv` and the sandbox cannot access the shared uv cache (`pytest`,
  `mypy`, and `uv build` were unavailable).

## Notes

- No browser UI was added; the deterministic terminal surface is intentionally
  the accessible proof for this package and avoids a new framework.
- No SQLite, provider SDK, recall implementation, or root README/submission
  file was changed.
