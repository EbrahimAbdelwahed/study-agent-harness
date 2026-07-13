# Task Bead: grounded-answer-integration Integrate canonical prompts and grounded answers through the generic engine

Status: Open
Priority: P1
Type: task
Depends On: grounded-answer-core, model-adapter-contracts
Run ID: `20260711-oss-harness-v01-batch5`
Spec: `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`

## Worker Profile

create `grounded-answer-integration-worker`

Rationale:

No reusable specialization selected yet.

## Context

The independent behavior and transport contracts must meet through one generic engine seam and prove the complete offline grounded-answer flow without special-casing the built-in skill.

## What To Do

- Add a generic prompt-composer runtime registry/port and compose ModelStep bindings into canonical messages before ModelPort.generate.
- Keep metadata local-only while retaining prompt composition and model invocation provenance in trusted outputs/traces needed by validation.
- Run grounded_answer_flow with real composer/validators and scripted tools/model; prove insufficient terminates before model and only validated output reaches the final step.
- Add adversarial end-to-end evals for supported/synthesis/conflict/injection/malformed/forged/stale-handle/course-profile behavior.
- Run the identical canonical request through the OpenAI-compatible fake transport and scripted adapter.

## Likely Files / Packages

- `src/study_agent/playbooks/runtime.py`: generic prompt-composer runtime contract
- `src/study_agent/playbooks/engine.py`: generic composition/invocation integration
- `tests/integration/test_grounded_answer_end_to_end.py`: complete offline flow
- `tests/evals/test_grounded_answer_fixtures.py`: adversarial behavior
- `tests/architecture/test_import_boundaries.py`: adapter/core boundary coverage

## Acceptance Criteria

- [ ] No semantic prompt input remains only in metadata and HTTP never transmits metadata.
- [ ] The engine has no grounded-answer/provider/model-name conditional.
- [ ] The identical skill/playbook and canonical composed request work through both adapters.
- [ ] Insufficient evidence makes zero model calls and invalid answers cannot reach a commit-capable tool.
- [ ] All offline tests, static checks, architecture gates, and adversarial evals pass.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_grounded_answer_end_to_end.py tests/evals/test_grounded_answer_fixtures.py tests/architecture`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output

## Out Of Scope

- Session events/persistence, typed public tools, CLI/export, semantic judges, network-required CI, and product scope.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
