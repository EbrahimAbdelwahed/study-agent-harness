# Worker Brief: TUT-03C2A tests

## Goal

Independently pin the pure contracts and validator behavior of the two C2A
built-in tutor capability packages now exported from `study_agent.capabilities`,
`playbooks.builtin`, `prompts`, and `skills.builtin`.

## Allowed Files

- `tests/unit/capabilities/test_builtin_capability_packages.py`

## Forbidden Files

- All production files, other tests, docs/specs, adapters, state/events/sessions,
  tools, `sbobby-web`, and repository configuration.

## Invariants

- Do not weaken implementation behavior to satisfy tests.
- Use real package objects and real `CapabilityBinding`; do not reproduce their
  implementation in fixtures.
- Assertions target public contracts, semantic safety, and observable outputs,
  not private line-by-line implementation.

## Acceptance Criteria

- Parametrically verify manifest/skill/playbook/prompt/pins/binding closure,
  exact input envelopes, one-model linear flow, `source.search@1` only, empty
  writes, provider neutrality, exact gated-dialogue default, and no package
  self-registration.
- Verify evidence gate sufficient/insufficient/conflicting/malformed behavior.
- Verify readiness clarifies only null target/scope and defaults null assessment
  format to free response.
- Verify explanation citation resolution and fail-closed unknown/stale handles.
- Verify assessment count, formats, canonical citations, deterministic derived
  IDs, duplicate prompt rejection, and rejection of answer/rubric/grade/attempt/
  mastery/schedule/provider fields.
- Verify assessment public output contains exactly
  `id/kind/prompt/options/citations` per question.

## Verification

- `.venv/bin/pytest -q tests/unit/capabilities/test_builtin_capability_packages.py`
- Relevant existing capability/playbook/grounding tests.
- `.venv/bin/ruff check tests/unit/capabilities/test_builtin_capability_packages.py`
- `MYPYPATH=src .venv/bin/mypy --strict tests/unit/capabilities/test_builtin_capability_packages.py`
- `git diff --check`
