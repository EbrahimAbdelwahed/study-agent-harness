# Worker Brief: TUT-03C2B integration and evals

## Goal

Prove both built-in tutor packages execute truthfully through the real
authority-bound gateway with request-scoped source search, canonical prompt
composition, validators, scripted models, durable checkpoints, and no mutation
of the seven public StudyTools.

## Allowed Files

- `tests/integration/test_builtin_capability_gateway.py`
- `tests/evals/test_builtin_tutor_capability_fixtures.py`

## Forbidden Files

- All production files, other tests, docs/specs, adapters, state/events/sessions,
  tools, `sbobby-web`, and repository configuration.

## Invariants

- Use the real manifests, binding factories, playbooks, validators,
  `StudyCapabilityGateway`, `PlaybookEngine`, `BoundSourceSearchExecutor`,
  `CanonicalPromptComposer`, durable run store, and `ScriptedModel`.
- Do not create a second run/state owner or mock away gateway authority,
  checkpoint recovery, citation resolution, or prompt composition.
- Offline only; no DeepSeek/OpenAI/network call.
- Keep fixtures small and shared within each authorized file; assert observable
  behavior rather than private implementation details.

## Acceptance Criteria

- Direct sufficient explain and assess complete without suspension, with one
  search and one model call; outputs are grounded/questions-only.
- Null target/scope suspends once, executes no model before resume, then resumes
  exactly the same generation and completes; null assessment format defaults to
  free response.
- Insufficient/conflicting evidence terminates before dialogue/model execution.
- Same idempotency identity with changed input conflicts without a second model;
  dependency drift at resume reports stale; altered authority/continuation fails
  without new effects; exact completed retry observes the persisted result.
- A fresh engine/gateway over the same run store recovers suspended/completed
  work; cancellation/interruption stays truthful and does not double-execute.
- Structured-output JSON fallback remains schema/integrity validated.
- Deterministic evals cover injection-shaped evidence and continuation data,
  explanation citation closure, assessment counts/formats, rejection of unknown
  handles/solution fields, and unchanged prompt policy/schema/tool declarations.
- The exact seven-tool `(name, version, fingerprint)` snapshot is unchanged.

## Verification

- `.venv/bin/pytest -q tests/integration/test_builtin_capability_gateway.py tests/evals/test_builtin_tutor_capability_fixtures.py`
- Existing gateway recovery and public tool contract tests.
- `.venv/bin/ruff check tests/integration/test_builtin_capability_gateway.py tests/evals/test_builtin_tutor_capability_fixtures.py`
- `MYPYPATH=src .venv/bin/mypy --strict tests/integration/test_builtin_capability_gateway.py tests/evals/test_builtin_tutor_capability_fixtures.py`
- `git diff --check`
