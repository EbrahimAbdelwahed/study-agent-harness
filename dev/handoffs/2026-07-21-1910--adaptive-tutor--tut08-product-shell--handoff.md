# Handoff: TUT-08 Build Week product shell

Date: 2026-07-21 19:10
Area: adaptive-tutor / product shell

## Current State

The branch contains a focused terminal product-shell tracer and an installable
`study-agent-shell` command. TUT-08 remains in progress because the browser
journey and full environment gates were not claimed; the terminal proof is
deterministic and offline.

## Completed

- Public-contract-only `ProductShell` view/status adapter.
- Immediate bounded free-form entry and host result mapping.
- Optional due-review seam with safe degraded fallback.
- Offline shell command reusing the existing anatomy host demo.
- Focused unit/integration tests and Build Week sample/eval/video docs.

## Remaining

- Run pytest, strict mypy, and clean wheel smoke in the repository's provisioned
  environment before considering the bead complete.
- Decide whether a separate browser surface is needed; none is required for
  the deterministic terminal acceptance currently documented.

## Verification

- Ruff, compileall, CLI JSON smoke, and `git diff --check`: passed.
- Pytest/mypy/uv build: not runnable here because dependencies/cache are absent
  or sandbox-inaccessible.
