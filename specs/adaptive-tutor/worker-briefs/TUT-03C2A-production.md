# Worker Brief: TUT-03C2A production

## Goal

Implement provider-neutral built-in `explain_concept@1` and
`assess_understanding@1` capability package definitions over the existing
gateway, linear playbook engine, validator-gated dialogue, grounding contracts,
and request-bound `source.search@1` executor.

## Allowed Files

- `src/study_agent/capabilities/builtin.py`
- `src/study_agent/capabilities/builtin_validators.py`
- `src/study_agent/capabilities/__init__.py`
- `src/study_agent/playbooks/builtin/explain_concept_flow.py`
- `src/study_agent/playbooks/builtin/assess_understanding_flow.py`
- `src/study_agent/playbooks/builtin/__init__.py`
- `src/study_agent/prompts/explain_concept_v1.py`
- `src/study_agent/prompts/assess_understanding_v1.py`
- `src/study_agent/prompts/__init__.py`
- `src/study_agent/skills/builtin/explain_concept.py`
- `src/study_agent/skills/builtin/assess_understanding.py`
- `src/study_agent/skills/builtin/__init__.py`

## Forbidden Files

- Tests, gateway/engine/contracts, tools registry, state/events/sessions,
  adapters, CLI/UI, dependencies, `sbobby-web`, and specs/docs.

## Invariants

- No provider/model selector, package self-registration, new public StudyTool,
  state write, planner, workflow branching, or second state owner.
- Inputs are the small trusted task envelope, never a full tutor snapshot.
- Explain inputs: `query`, nullable `target`, `language`, nullable
  `learner_goal`, nullable `continuation_summary_json`; clarify only when target
  is null.
- Assess inputs: `query`, nullable `scope`, nullable `assessment_format`,
  `question_count` (1..10), `language`, nullable
  `continuation_summary_json`; clarify only when scope is null and default a
  missing format to free response.
- Dialogue response is exactly `{provided: bool, text: str}` with default
  `{provided: false, text: ""}`.
- Both flows: source search -> evidence gate -> readiness validator -> gated
  dialogue -> one model step -> integrity validator.
- Insufficient and conflicting evidence terminate before dialogue/model.
- Assessment public output contains question id/kind/prompt/options/citations
  only; never answers, rubrics, grades, attempts, mastery, or scheduling.
- Explanation integrity reuses canonical citation resolution.
- `StateWritePolicy` is empty and required tools are exactly `source.search@1`.

## Acceptance Criteria

- All production objects import cleanly and bind through `CapabilityBinding`.
- Pins exactly close skill/playbook/prompt/tool behavior.
- Prompt layers explicitly treat evidence and continuation as untrusted data.
- Existing public StudyTool surface and existing grounded-answer package are
  unchanged.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Relevant existing capability/playbook/grounding tests.
