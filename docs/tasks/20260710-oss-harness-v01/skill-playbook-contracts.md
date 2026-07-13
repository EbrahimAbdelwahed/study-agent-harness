# Task Bead: skill-playbook-contracts Implement versioned skill and sequential playbook contracts

Status: Completed
Priority: P1
Type: task
Depends On: core-domain-contracts
Run ID: `20260710-oss-harness-v01`
Spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Worker Profile

create `skill-playbook-contract-worker`

Rationale:

No reusable specialization selected yet.

## Context

ADR-0002 requires pedagogical behavior to live in model-independent skill packages and playbooks from v0.1 rather than in provider adapters.

## What To Do

- Implement validated semantic identifiers and immutable SkillPackage manifests for schemas, layered prompts, policies, tools, capabilities, fallbacks, validators, fixtures, and referenced playbooks.
- Implement the trusted sequential playbook AST for tool, model, dialogue, and validate steps plus version pins and checkpoint data contracts.
- Implement capability negotiation that succeeds, selects only an explicitly declared portable fallback, or fails before execution.
- Add contract tests proving skill/playbook definitions cannot branch on provider or model names.

## Likely Files / Packages

- `src/study_agent/skills/`: skill manifests, registry contracts, prompt layers, policies, capabilities, and fallbacks
- `src/study_agent/playbooks/`: sequential AST, version pins, checkpoint and trace contracts
- `tests/unit/skills/`: manifest and capability tests
- `tests/unit/playbooks/`: AST, pins, and validation tests
- `tests/contract/`: provider-neutral behavior-boundary tests

## Acceptance Criteria

- [x] A skill package fully describes behavior inputs without referencing a provider or model name.
- [x] The v0.1 AST accepts only sequential tool, model, dialogue, and validate steps.
- [x] Version pins cover skill, playbook, prompt, tool behavior, model adapter, and state contracts.
- [x] Capability negotiation has deterministic supported, declared-fallback, and unsupported outcomes.
- [x] No prompt text, grading rule, retrieval policy, or domain transition is placed in a model adapter contract.

## Verification

- `python3 -m pytest tests/unit/skills tests/unit/playbooks tests/contract`: expected to pass or produce documented output
- `python3 -m mypy src/study_agent/skills src/study_agent/playbooks`: expected to pass or produce documented output
- `python3 -m ruff check src/study_agent/skills src/study_agent/playbooks tests/unit/skills tests/unit/playbooks tests/contract`: expected to pass or produce documented output

## Out Of Scope

- Playbook execution engine, retries, loops, conditions, parallelism, untrusted packages, marketplace, grounded-answer prompt content, and real model adapters.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
