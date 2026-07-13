# Worker Profile: model-adapter-worker

Generated: 2026-07-11
Source task: `docs/tasks/20260711-oss-harness-v01-batch5/model-adapter-contracts.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `model-adapter-contracts Implement scripted and generic OpenAI-compatible model adapters`.

## Mandate

Complete recurring work shaped like `model-adapter-contracts` without redesigning the feature.

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
- `docs/tasks/20260711-oss-harness-v01-batch5/model-adapter-contracts.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/ports/model.py`: portable model contracts
- `src/study_agent/adapters/model/`: scripted and OpenAI-compatible adapters
- `tests/contract/model/`: reusable conformance suite
- `tests/unit/adapters/model/`: translation, protocol, error, redaction tests
- `tests/integration/test_openai_compatible_smoke.py`: opt-in skipped smoke

May inspect:

- `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260711-oss-harness-v01-batch5/model-adapter-contracts.md`
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
-   - Both adapters satisfy one ModelPort conformance suite with structurally declared capabilities.
-   - Scripted calls are exact, deterministic, immutable, and never access environment/network.
-   - HTTP construction/import is inert and all default translation tests use an injected fake transport.
-   - Metadata and secret/content sentinels never appear in HTTP bodies, reprs, or safe public errors.
-   - Unsupported streaming/cancellation is explicit and never advertised; no provider/model-name branching exists.

## Verification

Run:

```bash
`.venv/bin/python -m pytest tests/contract/model tests/unit/adapters/model tests/integration/test_openai_compatible_smoke.py`: expected to pass or produce documented output
`.venv/bin/python -m ruff check src/study_agent/ports/model.py src/study_agent/adapters/model tests/contract/model tests/unit/adapters/model`: expected to pass or produce documented output
`.venv/bin/python -m mypy src/study_agent/ports/model.py src/study_agent/adapters/model tests/contract/model tests/unit/adapters/model`: expected to pass or produce documented output
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
