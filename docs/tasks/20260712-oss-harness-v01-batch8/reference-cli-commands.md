# Task Bead: reference-cli-commands Implement reference CLI commands and JSON boundary

Status: Open
Priority: P1
Type: task
Depends On: local-repository-composition, deterministic-export
Run ID: `20260712-oss-harness-v01-batch8`
Spec: `<spec path>`

## Worker Profile

create `reference-cli-worker`

Rationale:

No reusable specialization selected yet.

## Context

The stdlib CLI must expose the approved host workflow without duplicating study behavior.

## What To Do

- Implement parser, output/error boundary, and all approved commands.
- Wire ask to the existing GroundingAskService and export to ExportService.

## Likely Files / Packages

- src/study_agent/cli
- pyproject.toml
- CLI tests

## Acceptance Criteria

- [ ] Exactly one JSON document reaches stdout in JSON mode.
- [ ] All canonical writes use existing services.
- [ ] Empty and insufficient outcomes succeed; operational/provider failures are safe nonzero errors.

## Verification

- `.venv/bin/python -m pytest tests/unit/cli tests/integration/test_reference_cli.py`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- Hosted transports, provider-specific behavior, generic agents.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
