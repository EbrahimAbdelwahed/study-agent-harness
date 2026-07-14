# Worker Brief: TUT-03B1 tests

## Goal

Pin effect-free inspection and the exact boundary between confirmed cancellation,
failure, and ambiguous process interruption.

## Allowed Files

- `tests/unit/playbooks/test_capability_run_inspection.py`
- `tests/integration/test_capability_run_recovery.py`

## Forbidden Files

- Production, existing tests, other fixtures, adapters, docs/specs, UI, and
  `sbobby-web`.

## Required Coverage

- Inspect running/suspended/completed/failed/cancelled with exact immutable
  values and zero extra effects.
- Exact input/pin/dependency mismatch and canonical payload/trace tampering fail
  with existing safe engine codes.
- Suspended inspection exposes exact DialogueStep id/index/request and stable
  checkpoint fingerprint.
- Model error and finish-reason cancellation persist cancelled result/status/
  trace; generic model error persists failed.
- `asyncio.CancelledError` propagates and persisted state is never cancelled.
- `recover` still rejects suspended, failed, cancelled, and running inspection.

## Verification

- Focused tests, Ruff, strict mypy, existing recovery/CAS tests, and diff check.
