# Handoff: TUT-06D/E and essential capability-gap tracer

Date: 2026-07-18 15:40
Area: adaptive-tutor / capability-gap

## Current State

TUT-06A through TUT-06E are implemented; TUT-06E still needs its clean-wheel
build/install gate before Done. The reference host runs offline and
the optional Responses adapter is ready for an explicitly configured API-key
smoke. The capability-gap plane has a robust local-only observation tracer but
GAP-01/02 full policy remains open.

## Completed

- Optional OpenAI Responses decision adapter with strict schema/error/privacy
  boundary.
- Offline scripted and recorded-provider parity demo and real fault evals.
- Structured GAP observation contracts, atomic local SQLite aggregation and
  separate host reporting manifest/tool.
- Aggregated correctness/security review and approved fixes.

## Remaining

- Rerun `uv build` when cache access/usage permits.
- Choose whether the next GAP slice completes retention/rate/workaround policy
  or proceeds to another product/demo milestone; do not mark GAP-01/02 Done
  until their original acceptance criteria are satisfied.

## Important Context

- Live OpenAI smoke requires the optional SDK, explicit model, named API-key
  environment variable and opt-in gate. ChatGPT subscription is unsupported.
- Reporting is local observation only and must never be described as automatic
  improvement or issue creation.

## Verification

- 1664 tests passed, 3 expected skips; Ruff, strict mypy and diff check passed.
- Final semantic/security re-review: APPROVE.
