# Task Bead: reference-cli-release-gates Prove offline CLI flow, packaging, docs, and release behavior

Status: Open
Priority: P1
Type: task
Depends On: reference-cli-commands
Run ID: `20260712-oss-harness-v01-batch8`
Spec: `<spec path>`

## Worker Profile

create `cli-release-test-worker`

Rationale:

No reusable specialization selected yet.

## Context

A locally green command module is insufficient until installation and the complete user journey are proven.

## What To Do

- Add offline init-through-export/doctor integration fixtures and external-agent example.
- Verify clean Python 3.12 wheel installation, manual fixture, replay/export determinism, and release documentation.

## Likely Files / Packages

- tests/integration/test_reference_cli.py
- README.md
- docs/examples
- packaging/CI files

## Acceptance Criteria

- [ ] The approved end-to-end journey passes without network or keys.
- [ ] Installed study-agent works on Python 3.12.
- [ ] Public docs explain external-agent integration and honest cancellation/index recovery semantics.

## Verification

- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `clean Python 3.12 build/install/CLI smoke`: expected to pass or produce documented output

## Out Of Scope

- GitHub remote publication, which remains the final release lane.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
