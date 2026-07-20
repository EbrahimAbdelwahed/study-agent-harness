# Worker Brief: TUT-04C0B1B profiled worker execution tests

## Goal

Independently prove the exact persisted selection receipt, public/execution
input split, proof/retry recovery, dependency isolation, and byte-identical
ordinary capability path.

## Allowed Files

- `tests/unit/flashcards/test_lesson_worker_contracts.py`
- `tests/unit/flashcards/test_lesson_worker_service.py`
- `tests/unit/capabilities/test_capability_bindings.py`
- `tests/unit/capabilities/test_flashcard_dispatch.py`
- `tests/unit/capabilities/test_gateway_worker_adapter.py`
- `tests/unit/capabilities/test_gateway.py`
- `tests/unit/workers/test_worker_service.py`
- `tests/unit/workers/test_verified_child_proof.py`
- `tests/integration/test_gateway_worker_proof_recovery.py`
- `tests/architecture/test_gateway_worker_adapter_boundaries.py`
- `tests/architecture/test_flashcard_capability_boundaries.py`
- `tests/architecture/test_lesson_worker_boundaries.py`

## Forbidden Files

- Production, other tests/fixtures, docs/specs, dependencies, configuration,
  profile implementations, provider code, artifacts/events/state, CLI, UI,
  StudyTools, and `sbobby-web`.

## Acceptance Criteria

- `ProfileTaskExpectation` exact-codec tests pin canonical receipt persistence,
  domain-separated derived profile fingerprint, expectation/request/task-index
  commitment, round trip, noncanonical/extra/missing fields, changed mode/
  selector/authority/basis/profile, and checkpoint/restart recovery.
- Pass valid hybrid default provenance and valid morphology trusted-metadata
  provenance with one exact `RevisionId`. Reject morphology `DEFAULT/HOST`,
  profile/descriptor mismatch, worker-context-derived provenance, and changed
  receipt with otherwise identical pins/task payload.
- Descriptor/adapter tests prove the task payload remains exactly query, scope,
  language, candidate ceiling, and continuation summary; execution adds only the
  canonical receipt. The exact `profile-sha256` expectation reference, binding,
  definition, pins, schema, authority, and receipt profile are required.
- Start, suspended continuation, resume, completion, B1 verification, proof
  create, proof reload, crash-after-proof-create, and exact retry all use the
  same execution-input fingerprint. Public and execution tampering, missing/
  extra reserved data, reordered/noncanonical receipt JSON, or changed
  descriptor fail before another model effect.
- Proof codec golden tests pin the old exact bytes when execution and public
  fingerprints are equal. Profiled proofs encode the additional fingerprint;
  redundant equal serialization, omission when unequal, unknown fields, and
  changed execution inputs fail closed. B1 receipt golden bytes and public input
  fingerprint remain unchanged.
- Dependency recording proves ordinary and profiled start/resume resolvers see
  exactly the manifest's public projection. Changing only the reserved receipt
  cannot alter dependencies. Model/tool/validator recording proves the receipt
  never enters effect arguments, prompt bindings, or model requests.
- Ordinary `CapabilityBinding` regression fixtures pin byte-identical gateway
  arguments/run inputs, B1 task and receipt, proof and proof slot, continuation,
  dependency inputs, and outcome mapping.
- Architecture tests forbid profile modules, provider SDKs, mutable registries,
  task caches, hidden receipt lookup, flashcard-to-worker import cycles, public
  manifest widening, and receipt access from effect bindings.

## Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/flashcards/test_lesson_worker_contracts.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/unit/capabilities/test_capability_bindings.py \
  tests/unit/capabilities/test_flashcard_dispatch.py \
  tests/unit/capabilities/test_gateway_worker_adapter.py \
  tests/unit/capabilities/test_gateway.py \
  tests/unit/workers/test_worker_service.py \
  tests/unit/workers/test_verified_child_proof.py \
  tests/integration/test_gateway_worker_proof_recovery.py \
  tests/architecture/test_gateway_worker_adapter_boundaries.py \
  tests/architecture/test_flashcard_capability_boundaries.py \
  tests/architecture/test_lesson_worker_boundaries.py
.venv/bin/ruff check \
  tests/unit/flashcards/test_lesson_worker_contracts.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/unit/capabilities/test_capability_bindings.py \
  tests/unit/capabilities/test_flashcard_dispatch.py \
  tests/unit/capabilities/test_gateway_worker_adapter.py \
  tests/unit/capabilities/test_gateway.py \
  tests/unit/workers/test_worker_service.py \
  tests/unit/workers/test_verified_child_proof.py \
  tests/integration/test_gateway_worker_proof_recovery.py \
  tests/architecture/test_gateway_worker_adapter_boundaries.py \
  tests/architecture/test_flashcard_capability_boundaries.py \
  tests/architecture/test_lesson_worker_boundaries.py
.venv/bin/mypy --strict \
  tests/unit/flashcards/test_lesson_worker_contracts.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/unit/capabilities/test_capability_bindings.py \
  tests/unit/capabilities/test_flashcard_dispatch.py \
  tests/unit/capabilities/test_gateway_worker_adapter.py \
  tests/unit/capabilities/test_gateway.py \
  tests/unit/workers/test_worker_service.py \
  tests/unit/workers/test_verified_child_proof.py \
  tests/integration/test_gateway_worker_proof_recovery.py \
  tests/architecture/test_gateway_worker_adapter_boundaries.py \
  tests/architecture/test_flashcard_capability_boundaries.py \
  tests/architecture/test_lesson_worker_boundaries.py
git diff --check
```

## Report

Report production mismatches, profile provenance cases, public/execution
fingerprints, ordinary golden-byte results, exact commands, and whether recovery
reused one durable model effect. Do not edit production/docs, commit, or
delegate.
