# Plan: TUT-08 Build Week product shell

Date: 2026-07-21 19:00
Area: adaptive-tutor / product shell

## Goal

Add a thin, conversation-first terminal consumer over the public tutor
snapshot, capability discovery, and host-result contracts. The shell must be
usable with incomplete learner context, expose material/evidence/conflict and
optional due-review state, and remain deterministic and offline by default.

## Scope

- In scope: `src/study_agent/demo/product_shell.py`, focused demo tests,
  a shell entry point, and product-shell documentation/status memory.
- Out of scope: SQLite/provider access, core tutor behavior, recall
  implementation, `sbobby-web`, root README, and submission/upload assets.

## Approach

1. Define immutable shell view/status values and narrow structural protocols
   for snapshot, capability discovery, conversation host, and optional due
   review reads.
2. Map public snapshot and host results to deterministic working, suspended,
   conflicted, needs-review, stale, degraded, and recovered views.
3. Provide a terminal renderer and one-command offline wrapper that reuses the
   existing anatomy demo trace rather than duplicating tutor behavior.
4. Add focused contract tests and run Ruff, mypy, pytest, and wheel smoke.

## Invariants

- The shell never imports SQLite, model SDKs, or provider adapters.
- Free-form learner text is bounded and displayed immediately; it is not
  treated as canonical learner context.
- Snapshot material, context, divergences, timeline, and sequence values are
  rendered as received from the public port.
- Optional due-review failure degrades visibly without preventing the rest of
  the conversation view.

## Verification

- `.venv/bin/python -m pytest tests/unit/demo tests/integration/demo/TUT08`
- `.venv/bin/python -m ruff check src/study_agent/demo tests/unit/demo tests/integration/demo/TUT08`
- `.venv/bin/python -m mypy src/study_agent/demo`
- `.venv/bin/python -m study_agent.demo.product_shell`
- `uv build`
