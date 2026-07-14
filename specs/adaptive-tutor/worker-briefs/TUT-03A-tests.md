# Worker Brief: TUT-03A tests

## Goal

Pin the public capability-manifest and discovery contract independently.

## Allowed Files

- `tests/unit/capabilities/`
- `tests/contract/capabilities/`
- `tests/architecture/test_capability_gateway_boundaries.py`

## Forbidden Files

- Production, existing tests, external fixtures, docs/specs, network/model
  adapters, UI, and `sbobby-web`.

## Required Coverage

- Closed statuses and strict public values.
- Stable discovery and duplicate rejection.
- Invalid schemas and provider/model selectors rejected.
- No ranking/next-action fields.
- Exact seven StudyTools and fingerprints unchanged.
- Domain/state/skills/playbooks do not import the gateway, provider, SDK, or UI.

## Verification

- Focused tests, Ruff, strict mypy, architecture tests, and diff check.
