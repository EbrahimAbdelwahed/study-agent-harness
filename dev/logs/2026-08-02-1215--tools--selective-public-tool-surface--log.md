# Log: selective public agent tool surface

Date: 2026-08-02 12:15 CEST
Area: tools

## Summary

Integrated the public agent-operation surface selectively on the active
`codex/adaptive-tutor-foundation` checkout as commit `5b07660`, without merging
the divergent `codex/public-tool-surface-main` history. The exact seven v0.1
study-tool manifests remain unchanged; a separately named 16-operation
inventory now adds thin, course-bound adapters over the active canonical course,
text-ingestion, session, artifact-view, and assessment-view owners.

Discovery is explicitly versioned as `agent-operations@2`. Recall is not a
runnable tool because the active checkout has no recall owner; discovery reports
it as `owner_unavailable`. Artifact proposal generation/acceptance and
assessment writes remain unavailable because their canonical services require
verified generated-owner, accepted-artifact, and session preconditions that are
not composed by `LocalRepository`.

## Files Changed

- `src/study_agent/tools/operations.py`: nine closed-schema owner adapters and
  the typed, complete `AgentOperationOwners` bundle.
- `src/study_agent/tools/{builtin,registry,schema,__init__}.py`: expanded
  inventory, course binding, capability/idempotency/error gates, declared
  ingestion bounds, and compatibility exports.
- `src/study_agent/cli/{repository,registry,commands}.py`: current-owner
  composition and v2 static discovery; no new CLI command handlers.
- `src/study_agent/operator_skill/SKILL.md` and
  `docs/examples/external_agent.py`: direct public-contract negotiation updates.
- `tests/unit/tools/test_public_operations_contract.py`: inventory,
  delegation, authority, idempotency, bounds, and safe-error contracts.
- Directly affected CLI/repository integration tests: exact inventory and
  real-owner course creation, ingestion, session lifecycle/turn, artifact, and
  assessment coverage.
- `dev/plans/2026-08-02-1135--tools--selective-public-tool-surface--plan.md`:
  audited selective-integration contract and exclusions.

## Verification

- Baseline before edits: focused tool/discovery suite passed (`38 passed`).
- `.venv/bin/python -m pytest -q tests/unit/tools tests/contract/tools tests/contract/cli/test_agent_operation_discovery.py tests/integration/test_offline_tool_composition.py tests/integration/test_operator_skill_release.py tests/integration/test_reference_cli_release.py tests/integration/test_tool_harness_parity.py tests/architecture`: passed (`175 passed`).
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed (`472 source files`).
- `.venv/bin/python -m pytest -q` before the final focused review fixes:
  `2139 passed`, `3 skipped`, and one
  pre-existing failure in `test_package_resource_path_is_the_only_skill_copy`
  because its repository-wide recursive scan sees `SKILL.md` copies inside the
  retained `.worktrees/` directory.
- `.venv/bin/python -m pytest -q -k 'not test_package_resource_path_is_the_only_skill_copy'`:
  passed (`2148 passed`, `3 skipped`, `1 deselected`).
- `git diff --cached --check`: passed before commit.
- Independent semantic/regression review: two findings fixed (bounded artifact
  proposal output and correct authorization/projection error classification),
  followed by a clean final verdict.

## Excluded Deliberately

- Historical/divergent KB substrate, recall/scheduling/FSRS, PDF workarounds,
  capability-gap changes, browser/product shell, demo/UI, README/CI/release
  engineering, and private-product cleanup from the source lane.
- KB-13 `EvidenceService` recomposition: the hardened service exists in the
  active tree but is not wired into `LocalRepository`; changing retrieval scope
  and indexes requires a separate approved integration.
- Every downstream-product and separate checkout/worktree action.

## Notes

- The active `SessionTurnService` can reject a learner turn after a previously
  recorded note when its continuation-summary projection is stale. The new
  adapter does not duplicate or repair that owner behavior; this is a separate
  canonical session-summary issue.
- Pre-existing modified/untracked repository files, including `README.md`, were
  preserved and excluded from both feature and log commits.
