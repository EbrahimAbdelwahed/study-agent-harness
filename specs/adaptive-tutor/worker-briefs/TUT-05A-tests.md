# Worker Brief: TUT-05A tests

## Goal

Independently pin the public assessment identities, exact event codecs,
authority/order invariants, reducer history, learner redaction, and composition
boundaries implemented by TUT-05A.

## Allowed Files

- `tests/unit/assessments/test_contracts.py`
- `tests/unit/assessments/test_events.py`
- `tests/unit/assessments/test_projection.py`
- `tests/contract/assessment/test_assessment_view_contract.py`
- `tests/integration/test_assessment_ledger_replay.py`
- `tests/architecture/test_assessment_boundaries.py`

## Forbidden Files

- All production files, other tests, docs/specs, adapters, prompts, skills,
  playbooks, capabilities, tools, models, services, recall/scheduling,
  dependencies, `sbobby-web`, and configuration.

## Acceptance Criteria

- Golden typed presentation/attempt/grade identities are deterministic and
  prove timestamps, model text, credentials, and unrelated payloads are not
  identity inputs.
- Every event payload round-trips byte-identically and rejects missing/extra
  fields, malformed response/provenance unions, invalid fingerprints, secret
  shapes, forbidden mastery/scheduling/learner-model keys, and wrong actor.
- Presentation tests use accepted assessment artifacts and reject missing,
  proposed, rejected, superseded, wrong-kind, fingerprint-drifted, or
  learner-view-leaking inputs.
- Closed-answer fixtures pin exact single-choice and canonical JSON-array
  multiple-choice representation, artifact option order, and reject fuzzy,
  comma-parsed, duplicate, unknown, or reordered encodings.
- Reducer ordering tests prove attempt-before-presentation,
  grade-before-attempt, and contest-before-grade fail; valid events have strict
  increasing sequence and preserve immutable prior state.
- Supersession tests require an active predecessor for the same attempt and keep
  predecessor plus contest history queryable. Duplicate command identities and
  cross-course/session references fail closed.
- Grade provenance fixtures distinguish deterministic from verified capability
  proof, forbid model provenance in deterministic results, require passed
  validators and rubric binding in verified results, and never persist secrets
  or provider-selection policy.
- The learner presentation view contains format/prompt/options and identifiers
  only; expected response, evaluation criteria, internal provenance, and source
  commitments are structurally absent.
- Replay from the same event sequence yields byte-identical projection and
  typed snapshots. Architecture tests pin inward imports, additive registration,
  no service/model behavior, no mastery event/state, no global learner
  aggregate, and exactly seven unchanged StudyTools.

## Verification

- New focused test files.
- Relevant existing artifact/session/event-store/export/architecture tests.
- `.venv/bin/ruff check tests`
- `git diff --check`

## Report

Report concrete semantic mismatches as findings. Do not edit production,
commit, or delegate.
