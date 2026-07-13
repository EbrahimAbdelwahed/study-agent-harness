# Worker Profile: skill-playbook-contract-worker

Generated: 2026-07-10
Source task: `docs/tasks/20260710-oss-harness-v01/skill-playbook-contracts.md`

## Reuse Trigger

Use this worker when a bead has the same implementation shape as `skill-playbook-contracts Implement versioned skill and sequential playbook contracts`.

## Mandate

Complete recurring work shaped like `skill-playbook-contracts` without redesigning the feature.

## Scope

In scope:

- Implement the scoped task behavior described by the linked bead and worker brief.

Out of scope:

- Unrelated refactors.
- Changing public behavior outside the task acceptance criteria.
- Making product, architecture, prompt-policy, or data-model decisions reserved for the orchestrator.

## Required Context

Read first:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/skill-playbook-contracts.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed

## Allowed Files

May edit:

- `src/study_agent/skills/`: skill manifests, registry contracts, prompt layers, policies, capabilities, and fallbacks
- `src/study_agent/playbooks/`: sequential AST, version pins, checkpoint and trace contracts
- `tests/unit/skills/`: manifest and capability tests
- `tests/unit/playbooks/`: AST, pins, and validation tests
- `tests/contract/`: provider-neutral behavior-boundary tests

May inspect:

- `docs/specs/oss-study-agent-harness-v0-1.md`
- private Flywheel build provenance (not distributed)
- `docs/tasks/20260710-oss-harness-v01/skill-playbook-contracts.md`
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
-   - A skill package fully describes behavior inputs without referencing a provider or model name.
-   - The v0.1 AST accepts only sequential tool, model, dialogue, and validate steps.
-   - Version pins cover skill, playbook, prompt, tool behavior, model adapter, and state contracts.
-   - Capability negotiation has deterministic supported, declared-fallback, and unsupported outcomes.
-   - No prompt text, grading rule, retrieval policy, or domain transition is placed in a model adapter contract.

## Verification

Run:

```bash
`python3 -m pytest tests/unit/skills tests/unit/playbooks tests/contract`: expected to pass or produce documented output
`python3 -m mypy src/study_agent/skills src/study_agent/playbooks`: expected to pass or produce documented output
`python3 -m ruff check src/study_agent/skills src/study_agent/playbooks tests/unit/skills tests/unit/playbooks tests/contract`: expected to pass or produce documented output
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
