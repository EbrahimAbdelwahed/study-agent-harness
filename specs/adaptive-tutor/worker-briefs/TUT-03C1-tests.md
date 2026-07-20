# Worker Brief: TUT-03C1 tests

## Goal

Pin the optional dialogue contract, both runtime paths, recovery receipts, and
legacy compatibility independently from production.

## Allowed Files

- `tests/unit/playbooks/test_optional_dialogue_contract.py`
- `tests/integration/test_optional_dialogue_lifecycle.py`

## Forbidden Files

- Production, existing tests, capabilities/builtins, tools/adapters/state,
  docs/specs, CLI/UI, and `sbobby-web`.

## Required Cases

- Gate freezes default; definition rejects run-input/model/tool/forward/same-step
  condition references and accepts a prior ValidateStep nested boolean.
- False condition performs validator then skips without suspension/model
  ambiguity; default is schema-valid and fingerprint/receipt bound.
- True condition suspends once, exact resume completes, and process interruption
  remains ambiguous under existing engine rules.
- Wrong condition type, invalid default, changed definition, canonical payload,
  skipped disposition/default/output fingerprint, and resume generation tamper
  fail closed without repeating effects.
- An unconditional legacy DialogueStep keeps its definition fingerprint and
  old receipt/recovery behavior.

## Verification

- Narrow tests, existing dialogue/recovery/CAS suites, Ruff, strict mypy, full
  offline suite, and diff check.
