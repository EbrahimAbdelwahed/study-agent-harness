# Task Bead: deterministic-export Implement deterministic credential-free export v1

Status: Open
Priority: P1
Type: task
Depends On: cli-persistence-prerequisites
Run ID: `20260712-oss-harness-v01-batch8`
Spec: `<spec path>`

## Worker Profile

create `deterministic-export-worker`

Rationale:

No reusable specialization selected yet.

## Context

The release requires portable documented manifests without leaking operational or secret state.

## What To Do

- Implement storage-neutral export DTO assembly and exact decoding.
- Implement an atomic deterministic filesystem writer and redaction/determinism contract tests.

## Likely Files / Packages

- src/study_agent/application/export.py
- src/study_agent/adapters/filesystem/export.py
- tests/contract/export

## Acceptance Criteria

- [ ] Unchanged canonical state exports byte-identically.
- [ ] Only allowlisted course/source/session/answer/event fields ship.
- [ ] No credentials, configuration, blobs, traces, paths, endpoints, or timestamps leak.

## Verification

- `.venv/bin/python -m pytest tests/contract/export`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- Import and CLI formatting.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
