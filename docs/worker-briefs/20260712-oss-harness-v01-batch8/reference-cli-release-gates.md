# Worker Brief: reference-cli-release-gates

## Assignment

Implement `reference-cli-release-gates` from `<spec path>`.

Task title: reference-cli-release-gates Prove offline CLI flow, packaging, docs, and release behavior

## Read First

- `<spec path>`
- `docs/tasks/20260712-oss-harness-v01-batch8/reference-cli-release-gates.md`
- private Flywheel build provenance (not distributed)
- `docs/worker-profiles/cli-release-test-worker.md`
- Project `AGENTS.md` files that apply to touched paths.

## Scope

You may change:

- Paths listed in the task bead after inspecting the codebase.

Do not change:

- Unrelated modules.
- Files reserved by another active worker.
- Public behavior outside the task acceptance criteria.

## Requirements

- Claim or reserve the bead before editing when `br`/Agent Mail are active.
- Inspect existing patterns before editing.
- Keep changes small and reviewable.
- Add or update tests for changed behavior.
- Update docs if public behavior changes.
- If a material decision is needed, create a decision request with `flywheel-runner.py decision-request` instead of burying the question in chat.

## Verification

Run the commands listed in the task bead. If a command cannot run, explain why.

## Report Back

Return:

- files changed;
- behavior implemented;
- verification results;
- unresolved questions;
- follow-up beads needed.
