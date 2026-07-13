# Worker Brief: AML-04 production

## Assignment

Implement `AML-04` from
`specs/agent-managed-lifecycle/slices/04-operator-skill-and-release.md`.

## Read First

- `specs/agent-managed-lifecycle/README.md`
- `specs/agent-managed-lifecycle/slices/04-operator-skill-and-release.md`
- `specs/agent-managed-lifecycle/beads/04-operator-skill-release.md`
- current CLI registry/commands and release tests
- `README.md`, `docs/examples/external_agent.py`, `pyproject.toml`, CI workflow

## Scope

You may change:

- `src/study_agent/operator_skill/__init__.py`
- `src/study_agent/operator_skill/SKILL.md`
- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/commands.py`
- `src/study_agent/__init__.py`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `README.md`
- `docs/examples/external_agent.py`
- `tests/contract/cli/test_agent_operation_discovery.py`
- `tests/contract/cli/test_operator_skill_contract.py`
- `tests/integration/test_operator_skill_release.py`

Do not change:

- tool/domain/application behavior, other tests/specs/docs, Sbobby, commits/push

## Requirements

- Create a concise workflow skill with only `name` and `description` frontmatter;
  use imperative instructions and no duplicate README/resources.
- Stable ID is `study-agent-operator`, version `1.0.0`; fingerprint the exact
  packaged bytes and expose only identity/version/fingerprint/extraction command.
- Extraction and discovery are repository-free, credential-free, network-free.
- The skill must preserve host authority, exact-seven StudyTools, event-sourced
  state, skill/playbook behavior, technical-only adapters, and stable retry IDs.
- Include the future 0.2 recovery rule `status → plan → apply --expect-plan NEW_SHA`;
  never recommend blindly replaying an old plan.
- Update package version consistently to 0.1.1 and make the wheel include the
  resource as the sole canonical copy.
- Do not claim live model availability in the offline journey.

## Verification

Run focused tests, full pytest/Ruff/mypy, skill quick validation, build, and a
clean installed-wheel extraction smoke. Do not commit or push.

## Report Back

Return files, behavior, exact gates, wheel evidence, and unresolved findings.
