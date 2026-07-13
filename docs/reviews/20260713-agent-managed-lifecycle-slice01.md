# Review Report: Agent-managed lifecycle slice 01

Date: 2026-07-13
Reviewer: code-quality-governor

## Findings

- [P2, closed] `src/study_agent/cli/registry.py`: `model_setting`
  initially advertised raw JSON although the CLI wire value is `NAME=JSON`.
  The descriptor now declares a repeated string and a focused contract test pins
  its type, required flag, repetition, and serialized default.

## Required Fixes

- None remaining.

## Test Gaps

- Full descriptor-to-argparse argument-semantic parity remains a P3 hardening
  opportunity. Command identity and nested parser surfaces are covered.
- The live provider smoke remains intentionally opt-in and was not run.

## Verification Commands

- `python -m pytest -q`: passed, 425 tests; one opt-in network smoke skipped.
- `python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 162 source files.
- `git diff --check`: passed.

## Architecture Notes

- `study_agent.cli.registry` is the single owner of parser callbacks, handlers,
  and serializable operation metadata.
- Repository-free discovery does not open SQLite, enumerate credentials, create
  an async event loop, contact a model, rebuild an index, or mutate the filesystem.
- Static discovery consumes the seven canonical class-owned StudyTool manifests;
  all existing fingerprints are unchanged.
- Event sourcing, skills/playbooks, and technical model-adapter boundaries are
  unaffected.

## Prompt / Eval Notes

- No prompt, model policy, RAG behavior, or eval fixture changed in this slice.

## Verdict

Approved after closing the P2 descriptor finding.
