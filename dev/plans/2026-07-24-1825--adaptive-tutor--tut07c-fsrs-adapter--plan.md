# Plan: TUT-07C optional py-fsrs adapter

Date: 2026-07-24 18:25 CEST
Area: adaptive-tutor / recall scheduling

## Goal

Implement the optional `fsrs==6.3.1` scheduling adapter behind the existing
provider-neutral `SchedulingPolicyPort`, with deterministic reconstruction from
canonical recall history and no optional dependency in base imports or state.

## Scope and ownership

- Allowed: `src/study_agent/adapters/scheduling/**`, `pyproject.toml` (the
  exact `recall` optional extra only), `tests/unit/adapters/scheduling/**`,
  `tests/contract/recall/**`, `tests/architecture/**`, and this bead's
  `dev/` plan/log/handoff files.
- Forbidden: sbobby-web, model/provider adapters, StudyTools/capability
  fingerprints, artifact/assessment behavior, exporters/TUT-07D, base
  dependencies, runtime network calls, or package objects in core DTOs/state.
  A minimal schema-preserving correction to the recall contract/reducer is in
  scope because conformance proved the former core-only policy fingerprint
  could not attest adapter configuration.

## Preflight evidence

The disposable Python 3.12 and 3.13 environments installed exact
`fsrs==6.3.1` with `uv`. The package exposes `Scheduler`, `Card`, `Rating`, and
`ReviewLog`; its metadata declares MIT License, `Requires-Python >=3.10`, and
version `6.3.1`. The API documents `review_duration` in milliseconds, matching
the core `latency_ms` DTO. `Scheduler` defaults include 21 model parameters and
fuzzing enabled, so the adapter passes an explicit reviewed parameter tuple,
retention, learning steps, relearning steps, maximum interval, and
`enable_fuzzing=False`.

## Design and invariants

1. Keep `fsrs` imports lazy and confined to the adapter module. Base imports
   and the provider-neutral port remain usable when the extra is absent.
2. Validate the installed distribution version from metadata before creating
   a scheduler or returning a decision; raise one actionable composition error
   and perform no canonical writes.
3. Map all four closed `RecallRating` values explicitly to the corresponding
   FSRS enum members. Normalize all input/review/output datetimes to aware UTC.
4. Reconstruct a fresh deterministic `Card` from the request's complete
   ordered history on each call. Use an internal deterministic integer card id;
   never serialize, expose, or return FSRS package objects or their repr/state.
5. Encode the explicit adapter configuration in a stable policy version and
   configuration fingerprint. The shared recall contract computes a
   domain-separated effective policy fingerprint from the complete core policy
   plus policy/implementation identities; the FSRS policy version embeds the
   full adapter descriptor fingerprint, so replay can verify every parameter
   without importing FSRS.
6. Return only `SchedulingResult`, recomputing the result fingerprint through
   the existing canonical helper. Do not write events or invoke a network.

The event field shape remains unchanged. Existing deterministic fake fixtures
were updated to the same generic effective-policy helper so old replay and
offline service tests continue to exercise the fail-closed contract.

## Acceptance criteria

- `project.optional-dependencies.recall == ["fsrs==6.3.1"]`; no base
  dependency or inward `fsrs` import.
- Missing `fsrs`, wrong installed version, malformed request/history, and
  non-aware/non-UTC output fail closed with actionable errors.
- Empty enrollment plus failed/hard/good/easy and mixed ordered histories
  produce deterministic receipts; repeated decisions are byte-equivalent.
- Receipt has exact `implementation_id="py-fsrs"` and
  `implementation_version="6.3.1"`; due time is aware UTC and not before
  enrollment or the latest review.
- Conformance tests assert request/history/result fingerprints, no package
  object leakage, exhaustive ratings, and architecture import boundaries.

## Verification

- Disposable `uv` Python 3.12 and (if available) 3.13 exact-extra install,
  API/license/version smoke.
- Focused adapter/conformance pytest; Ruff; strict mypy; import firewall and
  base import without `fsrs`; `uv build` base and `[recall]` metadata where
  practical; `git diff --check`.
