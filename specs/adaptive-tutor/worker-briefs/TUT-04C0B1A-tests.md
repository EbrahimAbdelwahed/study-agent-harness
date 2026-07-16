# Worker Brief: TUT-04C0B1A gateway-worker proof adapter tests

## Goal

Pin gateway conversion, exact resume-task identity, provenance redaction, and
atomic proof ownership under retry/restart/race.

## Allowed Files

- `tests/unit/capabilities/test_gateway_worker_adapter.py`
- `tests/unit/workers/test_verified_child_proof.py`
- `tests/integration/test_gateway_worker_proof_recovery.py`
- `tests/architecture/test_gateway_worker_adapter_boundaries.py`
- `tests/unit/workers/test_worker_service.py` (resume fake/assertions only)
- `tests/architecture/test_worker_isolation_boundaries.py` (signature/helper only)

## Forbidden Files

- Other production/tests/fixtures, exam/flashcard/artifact packages, specs/docs,
  dependencies, provider SDKs, StudyTools, and `sbobby-web`.

## Required Coverage

- Public definition helper preserves all golden values and engine/gateway/
  dispatch use it directly. Shared authority helper preserves B1 golden values
  and is used by B1/proof.
- B1 passes the exact durable task on first resume, claimed-response retry, and
  crash recovery. Changed task/continuation conflicts; no task registry exists.
- Recording gateway covers all outcomes/in-progress with one gateway call and
  no direct effect. Completed conversion requires exact prompt and ordered
  validate/fallback receipts; missing/extra/duplicate/reordered/tampered fails
  without rerunning validation.
- Proof codec rejects changed run/task/receipt/authority/pins/input/output/
  dependency/tool/model/prompt/validation, unknown fields, noncanonical bytes,
  and oversize state.
- Clean subprocess imports cover workers-first and capabilities-first so pytest
  module ordering cannot hide a public-package cycle.
- Even with an exact task/authority/B1 receipt, changing recovered dependencies,
  a declared tool output/step/tool/value, or model id/response id/usage fails
  before ownership; stored proof is derived from the exact recovered run.
- Proof load requires exact task + run + completed receipt + parent, rejects a
  changed task before returning a view, and recomputes shared authority. Assert
  owner bytes contain only task fingerprint—not task bytes or raw inputs.
- One child-run owner slot: identical retry/restart succeeds, competing receipt/
  proof/authority conflicts, concurrent create yields one owner. Store/codec/
  oversize failure yields FAILED before B1 completion; crash after create reuses
  proof without another child effect.
- View contains only the pinned sanitized fields. Assert absence of
  `VerifiedRunRecord`, raw inputs/traces/other outputs/messages/requests,
  malformed attempts, credentials, principal ids, and write authority.
  Technical receipt accepts only adapter id/version, model id, nullable response
  id, optional usage. Cover `response_id=None` as valid and unchanged.
- Architecture keeps proof operational/provider-neutral, B1 views unchanged,
  and adds no events, StudyTools, or exam/flashcard dependency.

## Verification

- `PYTHONPATH=. .venv/bin/pytest -q tests/unit/capabilities/test_gateway_worker_adapter.py tests/unit/workers/test_verified_child_proof.py tests/integration/test_gateway_worker_proof_recovery.py tests/architecture/test_gateway_worker_adapter_boundaries.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/unit/playbooks tests/unit/workers tests/unit/capabilities/test_flashcard_dispatch.py tests/integration/test_capability_gateway_lifecycle.py tests/contract/tools/test_public_tool_contract.py`
- `.venv/bin/ruff check <new production and test files>`
- `.venv/bin/mypy --strict <new production files>`
- `PYTHONPATH=. .venv/bin/pytest -q`
- `git diff --check`
