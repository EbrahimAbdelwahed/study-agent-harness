# Worker Brief: TUT-03B2 tests

## Goal

Prove the authority, idempotency, suspension-generation, and outcome boundaries
of the capability gateway independently from its implementation.

## Allowed Files

- `tests/unit/capabilities/test_gateway_contracts.py`
- `tests/integration/test_capability_gateway_lifecycle.py`
- `tests/architecture/test_capability_gateway_boundaries.py`

## Forbidden Files

- Production, adapters/providers, tools, canonical events/state, sessions,
  existing tests, docs/specs, CLI/UI, `sbobby-web`.

## Required Cases

- Binding rejects manifest/skill/playbook/pin/schema/output/suspension mismatch.
- Start rejects missing session/idempotency, untrusted principal, missing grant,
  invalid input, and duplicate dependency identities before engine effects.
- Run/authority identity is stable under correlation/model-run changes and
  changes under principal/course/session/grant/idempotency/manifest changes.
- Completed and terminated outcomes contain verified recovery; suspended binds
  the exact dialogue generation; cancelled/failed/stale never carry verified
  output.
- Exact duplicate start converges; changed input conflicts; dependency drift is
  the only stale path; ambiguous RUNNING is retryable in-progress.
- Exact resume and concurrent CAS losers converge only when response,
  suspension fingerprint, step/index, definition, manifest, pins, inputs,
  dependencies, authority, and retry identity match. Token replay against a
  later dialogue or changed response fails closed.
- Architecture tests forbid provider/adapter/tool-registry imports and preserve
  the exact seven StudyTools and their fingerprints.

## Verification

- Narrow red/green tests, Ruff, strict mypy, full offline suite, and diff check.
