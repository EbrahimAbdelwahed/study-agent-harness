# Task Bead: grounded-answer-core Implement the portable grounded-answer behavior package

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch5`
Spec: `docs/specs/oss-harness-v0-1-grounded-answer-and-model-adapters.md`

## Worker Profile

create `grounding-prompt-worker`

Rationale:

No reusable specialization selected yet.

## Context

The retrieval spine exists, but prompt composition, evidence handles, grounded output decoding, and deterministic integrity policy must live in the skill/playbook layer rather than adapters.

## What To Do

- Define generic versioned prompt composition contracts and canonical JSON rendering with exact layer-input validation.
- Implement grounded_answer.v1 six-layer prompt definitions, strict answer-draft schema, canonical evidence envelope, and trusted citation reconstruction.
- Implement evidence-sufficiency and answer-integrity validator executors over SourceContentPort.
- Define grounded_answer@1.0.0 and grounded_answer_flow@1.0.0 using only the accepted sequential AST and canonical IDs.
- Add deterministic unit/contract fixtures including injection strings, conflict, unknown handles, forged extra fields, and course-profile variation.

## Likely Files / Packages

- `src/study_agent/prompts/`: prompt contracts, composer, and grounded_answer.v1 layers
- `src/study_agent/grounding/`: evidence codec, answer decoder, and validators
- `src/study_agent/skills/builtin/`: grounded_answer package
- `src/study_agent/playbooks/builtin/`: grounded_answer_flow definition
- `tests/unit/prompts`, `tests/unit/grounding`, `tests/unit/skills`, `tests/unit/playbooks`: behavior contracts

## Acceptance Criteria

- [ ] Six layers appear exactly once in canonical order and identical inputs produce identical messages/fingerprint.
- [ ] The model-facing schema contains only status, segment text/kind, evidence handles, and unsupported note.
- [ ] Every accepted handle maps to and re-resolves an exact trusted citation; malformed or forged output fails closed.
- [ ] Insufficient evidence terminates before model execution and trusted conflict cannot collapse to answered.
- [ ] No provider/model selector, SDK, network, SQLite object, or product behavior enters the core.

## Verification

- `.venv/bin/python -m pytest tests/unit/prompts tests/unit/grounding tests/unit/skills tests/unit/playbooks`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/prompts src/study_agent/grounding src/study_agent/skills src/study_agent/playbooks tests/unit`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/prompts src/study_agent/grounding src/study_agent/skills src/study_agent/playbooks tests/unit`: expected to pass or produce documented output

## Out Of Scope

- Model transport, session persistence/events, CLI/tools, semantic entailment, provider branches, and product scope.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
