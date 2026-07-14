# Worker Brief: TUT-03A production

## Goal

Add the smallest public, model-independent capability manifest and closed
discovery registry needed before execution is exposed.

## Allowed Files

- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/registry.py`
- `src/study_agent/capabilities/__init__.py`
- `src/study_agent/ports/capability.py` only if discovery needs a protocol
- `src/study_agent/ports/__init__.py` for exports only
- `src/study_agent/cli/repository.py` for composition only

## Forbidden Files

- Tests, engine/runtime/store, skills, playbooks, prompts, tools, sessions,
  events, reducers, export, model adapters, UI, docs/specs, and `sbobby-web`.

## Fixed Contract

- Only trusted composition-root capabilities are discoverable; runtime/model
  output cannot self-register.
- Identity is portable and versioned. Strict input/output JSON schemas use the
  existing schema validator.
- Outcome status is exactly `completed`, `suspended`, `terminated`,
  `cancelled`, `stale`, and `failed`, though execution lands in TUT-03B.
- Manifests expose authority and suspension support, never provider/model,
  next-action, ranking, or learner-hypothesis fields.
- Discovery is deterministic and duplicate identities fail closed.
- Do not modify or wrap `StudyToolRegistry`.

## Verification

- Ruff, strict mypy, exact-seven-tool/architecture tests, and diff check.
