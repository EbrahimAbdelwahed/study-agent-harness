# Worker Brief: AML-03 production

## Assignment

Implement `AML-03` from
`specs/agent-managed-lifecycle/slices/03-explicit-lifecycle-and-retry.md`.

## Read First

- `specs/agent-managed-lifecycle/README.md`
- `specs/agent-managed-lifecycle/slices/03-explicit-lifecycle-and-retry.md`
- `specs/agent-managed-lifecycle/beads/03-explicit-lifecycle-and-retry.md`
- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/commands.py`
- existing CLI release/retry tests

## Scope

You may change:

- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/commands.py`
- `tests/contract/cli/test_explicit_lifecycle.py`
- `tests/integration/test_reference_cli_release.py`

Do not change:

- tools/repository composition, CLI main, other tests, specs/docs, versions,
  packaging, or files outside `study-agent-harness`

## Requirements

- Delegate only to existing projection/course/session services; no second state
  or lifecycle abstraction.
- Course list must use deterministic canonical projections.
- Session start requires a host-supplied `--session-id` and uses existing
  idempotent `SessionService.start()`.
- Session get is read-only and course-scoped.
- Discovery metadata must distinguish legacy automatic ask convenience from the
  stable agent-safe session/idempotency path.
- Model arguments remain unable to select course/session/authority/idempotency.
- Preserve current JSON envelopes and legacy command behavior.

## Verification

Run focused lifecycle/release tests, Ruff, and mypy from the bead. Do not commit
or push.

## Report Back

Return files, behavior, exact gates, unresolved findings, and recovery evidence.
