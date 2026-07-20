# Worker Brief: TUT-03C1 production

## Goal

Add the constrained validator-gated optional dialogue primitive accepted in
ADR-0007 while preserving the linear playbook/checkpoint model.

## Allowed Files

- `src/study_agent/playbooks/contracts.py`
- `src/study_agent/playbooks/engine.py`
- `src/study_agent/playbooks/__init__.py`

## Forbidden Files

- Capabilities/gateway, skills/prompts/builtins, tools, validators, adapters,
  state/events/sessions, CLI/UI, tests/docs/specs, and `sbobby-web`.

## Fixed Contract

- Introduce immutable `DialogueGate(suspend_when, default_response)` and an
  optional `gate` on `DialogueStep`; unconditional construction and fingerprint
  payload remain byte-compatible.
- The reference is STEP_OUTPUT, has a non-empty path, and must resolve to a
  previous `ValidateStep` output. Reject run-input, model/tool output, forward,
  and same-step references at definition construction.
- Preflight validates the default against the dialogue response schema before
  any executor effect. Runtime requires the resolved condition to be exactly
  bool.
- True uses the existing suspended trace/checkpoint/result and resume path.
  False writes the frozen default, records STARTED+COMPLETED with exact
  `dialogue_disposition=skipped` and output fingerprint, then continues.
- Definition fingerprints include the gate only when present. Checkpoint-shape
  validation recomputes the prior validator condition: false requires skipped
  trace/default; true requires suspended+completed resume receipt. Old
  unconditional dialogue receipts remain accepted unchanged.
- Any condition/default/receipt mismatch fails closed; do not add BranchStep,
  outcome/status/store changes, provider behavior, or canonical writes.

## Verification

- Ruff/strict mypy, existing engine/recovery/CAS/dialogue tests, new focused
  tests from the independent worker, full offline suite, and diff check.
