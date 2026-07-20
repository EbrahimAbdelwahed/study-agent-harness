# Worker Brief: TUT-03B1 production

## Goal

Extend PlaybookEngine with effect-free validated inspection and truthful
transport-confirmed cancellation, without weakening successful recovery.

## Allowed Files

- `src/study_agent/playbooks/runtime.py`
- `src/study_agent/playbooks/contracts.py`
- `src/study_agent/playbooks/engine.py`
- `src/study_agent/playbooks/__init__.py`

## Forbidden Files

- Tests, capabilities, RunStore port/adapters/schema, skills, tools, sessions,
  events, model adapters, CLI, UI, docs/specs, and `sbobby-web`.

## Fixed Contract

- Add `RunStatus.CANCELLED`, `PlaybookRunStatus.CANCELLED`,
  `CancelledRunResult`, and a typed `InspectedRunRecord` that is not a verified
  success record.
- `inspect(run_id, definition)` reuses canonical `_load` validation and returns
  status, definition/checkpoint fingerprints, the exact persisted inputs, pins,
  dependencies, outputs, traces, next step, and suspended dialogue
  identity/request when applicable. Trusted callers compare those bindings;
  `recover` retains its stricter expected-binding proof.
- The checkpoint fingerprint is domain-separated SHA-256 over the exact
  canonical stored payload. Inspection performs no executor effect.
- A model `CANCELLED` error or finish reason becomes `EngineErrorCode.CANCELLED`;
  `_run` persists checkpoint `cancelled`, trace `cancelled`, and returns
  `CancelledRunResult`.
- Do not catch or translate `asyncio.CancelledError`, KeyboardInterrupt, SIGINT,
  or other BaseException. They may leave `running` and must remain ambiguous.
- `recover` continues to accept only completed/deterministically terminated
  checkpoints. Existing checkpoint schema stays version 1 and old statuses
  remain byte-compatible.

## Verification

- Ruff/strict mypy on changed source, existing playbook engine/recovery/CAS
  suites, architecture checks, and diff check.
