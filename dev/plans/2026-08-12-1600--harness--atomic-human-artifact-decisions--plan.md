# Plan: Atomic HUMAN artifact bulk decisions

Date: 2026-08-12 16:00
Area: Harness PF-07 artifacts

## Goal

Add one atomic, retry-stable command for applying an ordered batch of HUMAN
artifact revision decisions while preserving the existing shared event stream,
projection, and single-item decision behavior.

## Scope

### In scope

- `src/study_agent/artifacts/{contracts,events,service,projection,view,__init__}.py`
- `src/study_agent/ports/artifact.py`
- `src/study_agent/api/artifacts.py`
- Focused artifact unit/contract/integration replay and SQLite tests.
- This plan and the corresponding development log/handoff.

### Forbidden

- Cardine files, recall/assessment behavior or schema, database schema changes,
  new event types, new stores/outboxes, providers/UI, dependencies, and files
  outside the approved allowlist.

## Contract and invariants

1. A request contains 1–24 unique, ordered revision IDs and mixed ACCEPT/REJECT
   decisions; every target is a canonical proposed revision in one course and
   one session, and the actor is HUMAN.
2. Every target, predecessor, and idempotency identity is prevalidated before a
   single `EventStore.append` call containing the existing
   `study_artifact.decision_recorded` events. Invalid final items append zero
   events; no intra-batch dependency is allowed.
3. ACCEPT names exactly the current accepted predecessor (or `None`); REJECT
   never names a predecessor. Batch order is the request order and does not
   change validation state between items.
4. Per-item retry identities are deterministic functions of the bulk key,
   ordinal, and manifest hash. Exact retry/restart returns the original receipt
   with zero append; a changed manifest under the same bulk key conflicts.
5. The immutable receipt records request fingerprint, manifest fingerprint,
   start/end stream sequence, and per-item results. Existing single-item
   commands and replay remain unchanged.

## Approach

1. Add typed request/result/receipt contracts and deterministic manifest/retry
   fingerprint helpers.
2. Add event payload support for a bulk command using only existing decision
   event type/codecs; preserve existing projection semantics and expose the
   receipt through the view/API port.
3. Implement service prevalidation and one append batch, with idempotent exact
   retry and conflict handling.
4. Add contract, service, projection/replay, and SQLite atomicity tests,
   including invalid-last zero-write and mixed decision cases.

## Acceptance criteria

- The focused service/event/projection/replay/SQLite tests prove every
  invariant above, including zero append on invalid last item and exact retry.
- Existing artifact lifecycle and recall regression tests remain green.
- Ruff, mypy, and `git diff --check` pass for the changed scope.
- No database schema, event type, dependency, Cardine, provider, UI, or recall
  change is introduced.

## Verification

```text
uv run --python 3.13 --extra dev pytest -q tests/unit/artifacts tests/contract/artifacts tests/integration/test_artifact_repository_replay.py tests/integration/test_artifact_bulk_decisions.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_recall_ledger_replay.py tests/integration/test_recall_service.py
uv run --python 3.13 --extra dev ruff check src/study_agent/artifacts src/study_agent/ports/artifact.py src/study_agent/api/artifacts.py tests/unit/artifacts tests/contract/artifacts tests/integration/test_artifact_bulk_decisions.py
uv run --python 3.13 --extra dev mypy src/study_agent/artifacts src/study_agent/ports/artifact.py src/study_agent/api/artifacts.py
git diff --check
```
