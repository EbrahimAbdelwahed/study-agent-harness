# Task Bead: minimal-playbook-engine Implement the trusted sequential playbook engine

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260710-oss-harness-v01-batch2`
Spec: `docs/specs/oss-harness-v0-1-content-and-execution-spine.md`

## Worker Profile

create `sequential-playbook-engine-worker`

Rationale:

No reusable specialization selected yet.

## Context

The accepted AST, bindings, pins, checkpoints, capability negotiation, and ModelPort contracts need a minimal executor before grounded_answer can be implemented without embedding behavior in adapters.

## What To Do

- Implement a sequential PlaybookEngine for tool, model, dialogue, and validate steps only.
- Resolve run-input and previous-output DataBindings into immutable executor inputs.
- Preflight engine compatibility, pins, model capabilities, and exact tool behavior versions before effects.
- Use injected provider-neutral tool, validator, model, and run-store protocols with scripted fakes for tests.
- Implement validation continue/terminate semantics and dialogue suspend/resume with compatible pinned checkpoints and declared resume input.
- Produce immutable outputs/traces and explicit structured engine errors.

## Likely Files / Packages

- `src/study_agent/playbooks/engine.py`: sequential execution and binding resolution
- `src/study_agent/playbooks/runtime.py`: narrow executor/registry/result/error contracts if separation is useful
- `src/study_agent/playbooks/__init__.py`: explicit public exports
- `tests/unit/playbooks/`: preflight, binding, termination, and compatibility tests
- `tests/integration/test_playbook_engine.py`: complete and suspend/resume scripted flows

## Acceptance Criteria

- [ ] A representative question-search-model-validation-commit sequence resolves bindings and executes in order.
- [ ] Validation termination prevents all later executor calls and returns structured output.
- [ ] Dialogue suspension persists a pinned checkpoint and compatible resume continues exactly once from the next step.
- [ ] Capability, tool-version, pin, or checkpoint incompatibility fails before effects.
- [ ] No provider/model-name branch, retry loop, general condition, parallelism, or canonical domain write is introduced.
- [ ] Default tests are deterministic and network-free.

## Verification

- `.venv/bin/python -m pytest tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/playbooks tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/playbooks tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output

## Out Of Scope

- Production prompts, retrieval, grounded-answer domain commits, retries, loops, branches, parallel execution, provider adapters, Tau, and untrusted playbooks.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
