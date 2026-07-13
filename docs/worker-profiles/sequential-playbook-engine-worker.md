# Worker Profile: sequential-playbook-engine-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01-batch2/minimal-playbook-engine.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `minimal-playbook-engine Implement the trusted sequential playbook engine`.

## Mandate

Complete recurring work shaped like `minimal-playbook-engine` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01-batch2/minimal-playbook-engine.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/playbooks/engine.py`: sequential execution and binding resolution
- `src/study_agent/playbooks/runtime.py`: narrow executor/registry/result/error contracts if separation is useful
- `src/study_agent/playbooks/__init__.py`: explicit public exports
- `tests/unit/playbooks/`: preflight, binding, termination, and compatibility tests
- `tests/integration/test_playbook_engine.py`: complete and suspend/resume scripted flows

May inspect:

- `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01-batch2/minimal-playbook-engine.md`
- applicable `AGENTS.md` files

Do not edit:

- Files outside the bead's approved scope.
- Files reserved by another active worker.

## Forbidden Decisions

Stop and report back before deciding:

- architecture boundaries outside the task bead
- product behavior not covered by acceptance criteria
- new dependencies or provider choices
- data model or persistence changes not specified by the orchestrator

## Quality Gates

- Change stays within the task file/package scope.
- Acceptance criteria are implemented or explicitly reported as blocked.
- Verification commands from the task bead are run or a concrete reason is reported.
- Acceptance criteria from the bead remain the source of truth:
-   - A representative question-search-model-validation-commit sequence resolves bindings and executes in order.
-   - Validation termination prevents all later executor calls and returns structured output.
-   - Dialogue suspension persists a pinned checkpoint and compatible resume continues exactly once from the next step.
-   - Capability, tool-version, pin, or checkpoint incompatibility fails before effects.
-   - No provider/model-name branch, retry loop, general condition, parallelism, or canonical domain write is introduced.
-   - Default tests are deterministic and network-free.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/playbooks tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/playbooks tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
```

If verification cannot run, report the reason and the narrowest manual check completed.

## Report Format

Return:

- files changed;
- behavior implemented;
- verification results;
- profile constraints followed;
- unresolved questions;
- recommended next worker or review step.
