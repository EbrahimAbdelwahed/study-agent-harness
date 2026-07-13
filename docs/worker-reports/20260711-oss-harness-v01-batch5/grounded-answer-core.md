# Worker Report: grounded-answer-core

Status: complete
Run ID: `20260711-oss-harness-v01-batch5`
Task: `docs/tasks/20260711-oss-harness-v01-batch5/grounded-answer-core.md`
Brief: `docs/worker-briefs/20260711-oss-harness-v01-batch5/grounded-answer-core.md`
Agent: skill_playbook_contracts
Reported: 2026-07-11 11:29

## Files Changed

- src/study_agent/prompts: generic canonical six-layer prompt composition and grounded_answer.v1
- src/study_agent/grounding: evidence handles/codecs and deterministic integrity validators
- src/study_agent/skills/builtin and playbooks/builtin: canonical grounded_answer@1.0.0 package/flow

## Behavior Implemented

- Composes deterministic provider-neutral messages with exact input checking and fingerprints.
- Accepts model evidence handles only, reconstructs trusted citations, and fails closed on integrity violations.

## Verification

- .venv/bin/python -m pytest: 167 passed, 1 expected skipped
- .venv/bin/python -m ruff check .: passed in combined gate
- .venv/bin/python -m mypy: passed in combined gate

## Open Questions Or Blockers

- None.

## Follow-up Beads Needed

- Integrate PromptComposer generically into PlaybookEngine and run end-to-end adversarial fixtures.
