# Worker Brief: TUT-07A tests

## Goal

Independently pin recall identities, the provider-neutral scheduling port,
strict event codecs, authority/order invariants, projection replay, and FSRS/
Anki isolation implemented by TUT-07A.

## Allowed Files

- `tests/unit/recall/test_contracts.py`
- `tests/unit/recall/test_events.py`
- `tests/unit/recall/test_projection.py`
- `tests/contract/recall/test_scheduling_port_contract.py`
- `tests/contract/recall/test_recall_view_contract.py`
- `tests/integration/test_recall_ledger_replay.py`
- `tests/architecture/test_recall_boundaries.py`

## Forbidden Files

- All production files, other tests, docs/specs, dependencies/configuration,
  services, adapters, FSRS/Anki code, export/repository composition, prompts,
  skills, playbooks, capabilities, tools, models, `sbobby-web`, and the seven
  StudyTools.

## Acceptance Criteria

- Golden typed review/decision identities are deterministic and prove times,
  ratings, scheduler output, package data, credentials, and model text are not
  identity inputs.
- Configuration, history, and result fingerprint goldens use exact canonical
  bytes and change for every effective input, including review order, rating,
  occurrence time, latency, confidence, due time, policy version, and
  implementation version.
- Scheduling-port contract fixtures use only core DTOs. A structural fake can
  conform without importing `fsrs`; package objects, opaque state, floats, and
  mappings with extra fields are rejected at the boundary.
- Every event payload round-trips byte-identically and rejects missing/extra
  fields, malformed fingerprints, naive/non-UTC times, invalid confidence/
  latency/rating, secret shapes, forbidden package/export/mastery keys, and
  wrong actor.
- Reducer tests start from accepted hybrid and morphology flashcards and reject
  missing, proposed, rejected, superseded, wrong-kind, or cross-course targets.
- Ordering tests reject review-before-enrollment, duplicate enrollment,
  decision-before-review, two pending reviews, mismatched review triggers,
  skipped/reordered history, duplicate identities, and forged history/result
  fingerprints.
- Valid replay preserves initial schedule, every review, every matching applied
  decision, enrollment time, and command receipts byte-identically. Artifact
  supersession leaves historical recall rows intact at this ledger layer.
- Architecture tests prove domain/ports/recall import no `fsrs`, Anki, adapter,
  provider/model, CLI, storage, UI, or `sbobby-web` modules; no serialized card,
  review-log, deck/note id, ease factor, mastery event, or global aggregate
  exists; exactly seven StudyTools remain unchanged.
- Tests do not install or conditionally skip on `fsrs`. TUT-07A is fully green
  in the base zero-dependency environment.

## Verification

- New focused test files.
- Relevant existing artifact/assessment/event-store/architecture tests.
- `.venv/bin/ruff check tests`
- `git diff --check`

## Report

Report concrete semantic mismatches as findings. Do not edit production,
commit, or delegate.
