# Worker Profile: grounding-prompt-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-core.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `grounded-answer-core Implement the portable grounded-answer behavior package`.

## Mandate

Complete recurring work shaped like `grounded-answer-core` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-core.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/prompts/`: prompt contracts, composer, and grounded_answer.v1 layers
- `src/study_agent/grounding/`: evidence codec, answer decoder, and validators
- `src/study_agent/skills/builtin/`: grounded_answer package
- `src/study_agent/playbooks/builtin/`: grounded_answer_flow definition
- `tests/unit/prompts`, `tests/unit/grounding`, `tests/unit/skills`, `tests/unit/playbooks`: behavior contracts

May inspect:

- `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-core.md`
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
-   - Six layers appear exactly once in canonical order and identical inputs produce identical messages/fingerprint.
-   - The model-facing schema contains only status, segment text/kind, evidence handles, and unsupported note.
-   - Every accepted handle maps to and re-resolves an exact trusted citation; malformed or forged output fails closed.
-   - Insufficient evidence terminates before model execution and trusted conflict cannot collapse to answered.
-   - No provider/model selector, SDK, network, SQLite object, or product behavior enters the core.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/unit/prompts tests/unit/grounding tests/unit/skills tests/unit/playbooks`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/prompts src/study_agent/grounding src/study_agent/skills src/study_agent/playbooks tests/unit`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/prompts src/study_agent/grounding src/study_agent/skills src/study_agent/playbooks tests/unit`: expected to pass or produce documented output
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
