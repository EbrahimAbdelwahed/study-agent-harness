# Worker Dispatch: Harness Package Foundation

Date: 2026-08-09
Run ID: `20260809-harness-package-foundation`

## Orchestrator Instructions

Call `multi_agent_v1.spawn_agent` once per packet using the `spawn_agent` object in `worker-dispatch.json`.
Do not spawn two workers that own overlapping file scopes unless the task graph explicitly allows it.

## Packets

### `pf-02`

- Task: `docs/tasks/20260809-harness-package-foundation/pf-02.md`
- Brief: `docs/worker-briefs/20260809-harness-package-foundation/pf-02.md`
- br id: `study-agent-harness-integration-pf-02-17u`
- File hints: src/study_agent/api/authority.py, src/study_agent/domain/{errors,authority}.py, src/study_agent/application/errors.py, src/study_agent/ports/authority.py, tests/contract/test_public_failures.py, tests/contract/test_authority_context.py, tests/architecture/test_authority_boundaries.py

```text
You are a Codex worker implementing one scoped flywheel task.

You are not alone in this codebase. Other agents or the user may have active changes. Do not revert unrelated edits; inspect and work with the current tree.

Project: `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration`
Run ID: `20260809-harness-package-foundation`
Task ID: `pf-02`
- `br` bead id: `study-agent-harness-integration-pf-02-17u`

Read first:
- `docs/specs/harness-package-foundation.md`
- `docs/flywheel-runs/20260809-harness-package-foundation/context-pack.md`
- `docs/tasks/20260809-harness-package-foundation/pf-02.md`
- `docs/worker-briefs/20260809-harness-package-foundation/pf-02.md`
- Applicable `AGENTS.md` files for any path you touch.

Assignment:
- Implement only the task described by `docs/tasks/20260809-harness-package-foundation/pf-02.md` and `docs/worker-briefs/20260809-harness-package-foundation/pf-02.md`.
- Keep the change small, reviewable, and within the file/package scope listed in the task.
- If scope is unclear or product/architecture risk appears, write a decision request instead of guessing.
- Add or update tests for changed behavior.
- Run the verification commands listed in the task bead.

Coordination protocol:
- If `br` is available and a bead id is listed, claim/update that bead before editing.
- If Agent Mail is active, reserve the likely file paths before editing and release reservations at the end.
- Leave progress in the task bead or coordination thread if work is partial.

Final report format:
- Files changed:
- Behavior implemented:
- Verification commands and outcomes:
- Open questions or blockers:
- Follow-up beads needed:

```
