# Log: TUT-06D/E and essential capability-gap tracer

Date: 2026-07-18 15:40
Area: adaptive-tutor / capability-gap

## Summary

Completed TUT-06D and TUT-06E, including the clean-wheel build/install matrix.
Added an optional direct OpenAI Responses
decision adapter and a deterministic offline reference-host demo using the same
provider-neutral runner/gateway path as recorded Responses fixtures.

Implemented an intentionally partial GAP-01/02 tracer. An agent-facing host
tool can submit only closed structured missing-capability dimensions; trusted
host context supplies limitation and idempotency evidence; a dedicated local
SQLite plane atomically deduplicates and aggregates observations across restart.
It cannot execute, export, prioritize, open issues, invoke Flywheel, or modify
the harness.

## Architecture

- Responses requests use a provider-neutral strict decision schema, valid typed
  input message, `store=False`, bounded output, SDK retries disabled, explicit
  model id and API-key environment variable.
- Base imports retain zero runtime dependencies; the SDK is lazy and optional.
- SQLite GAP storage uses no-follow opening, retained-file-descriptor identity
  verification, exact per-operation schema checks, and `BEGIN IMMEDIATE`.
- Capability-gap reporting is separate from seven StudyTools, capability
  manifests, course events, learner evidence, and canonical tutor state.

## Review

- Aggregated review found invalid live Responses input shape, incomplete SDK
  error classification, SQLite path/schema/retry integrity gaps, overclaimed
  demo evidence, inert adversarial tests, nondeterministic smoke expectation,
  and configurable report manifest.
- All findings were fixed. Final targeted review: APPROVE.

## Verification

- Full offline pytest: 1664 passed, 3 expected skips.
- Ruff: clean across repository.
- Strict mypy: clean.
- `git diff --check`: clean.
- `uv build`: source distribution and universal wheel built successfully.
- Clean base-wheel Python 3.12 venv: public core contracts imported with no
  OpenAI SDK installed; the full offline reference-host demo completed with
  scripted/recorded parity.
- Clean `[openai]` wheel Python 3.12 venv: OpenAI 2.46.0 installed and the
  offline adapter import/configuration conformance contract passed without an
  API key or provider request.
- Closure rerun: 1664 tests passed, 3 expected skips; repository-wide Ruff and
  strict mypy over all 231 distributed source files passed. The broader
  test-typing invocation now reports pre-existing test-fixture errors under
  local mypy 2.3.0; no production module or TUT-06E closure file is implicated.

## Deferred GAP Scope

- Retention/rate policy, resolution, trusted workaround execution receipts,
  outbox/export, Flywheel import/proposal, promotion, transport and GitHub.
- GAP-01 and GAP-02 therefore remain open despite the essential tracer.
