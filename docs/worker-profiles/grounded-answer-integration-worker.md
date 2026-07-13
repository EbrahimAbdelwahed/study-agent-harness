# Worker Profile: grounded-answer-integration-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-integration.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `grounded-answer-integration Integrate canonical prompts and grounded answers through the generic engine`.

## Mandate

Complete recurring work shaped like `grounded-answer-integration` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-integration.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/playbooks/runtime.py`: generic prompt-composer runtime contract
- `src/study_agent/playbooks/engine.py`: generic composition/invocation integration
- `tests/integration/test_grounded_answer_end_to_end.py`: complete offline flow
- `tests/evals/test_grounded_answer_fixtures.py`: adversarial behavior
- `tests/architecture/test_import_boundaries.py`: adapter/core boundary coverage

May inspect:

- `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-integration.md`
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
-   - No semantic prompt input remains only in metadata and HTTP never transmits metadata.
-   - The engine has no grounded-answer/provider/model-name conditional.
-   - The identical skill/playbook and canonical composed request work through both adapters.
-   - Insufficient evidence makes zero model calls and invalid answers cannot reach a commit-capable tool.
-   - All offline tests, static checks, architecture gates, and adversarial evals pass.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/integration/test_grounded_answer_end_to_end.py tests/evals/test_grounded_answer_fixtures.py tests/architecture`: expected to pass or produce documented output
`.venv/bin/python -m pytest`: expected to pass or produce documented output
`.venv/bin/python -m ruff check .`: expected to pass or produce documented output
`.venv/bin/python -m mypy`: expected to pass or produce documented output
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
