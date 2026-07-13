# Task Bead: local-repository-composition Compose a strict non-secret local repository

Status: Open
Priority: P1
Type: task
Depends On: cli-persistence-prerequisites
Run ID: `20260712-oss-harness-v01-batch8`
Spec: `<spec path>`

## Worker Profile

create `local-composition-worker`

Rationale:

No reusable specialization selected yet.

## Context

CLI commands need one auditable local composition root without moving behavior into the adapter.

## What To Do

- Implement strict layout/config decoding.
- Compose existing event, blob, retrieval, session, run, prompt, playbook, and model ports behind generic adapter selection.

## Likely Files / Packages

- src/study_agent/cli/repository.py
- src/study_agent/cli/config.py
- focused unit/integration tests

## Acceptance Criteria

- [ ] No credential value is persisted.
- [ ] No provider/model branch enters domain, ports, prompts, skills, or playbooks.
- [ ] Repository initialization is offline, idempotent, and rejects incompatible collisions.

## Verification

- `.venv/bin/python -m pytest tests/unit/cli`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- CLI frontend and export format.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
