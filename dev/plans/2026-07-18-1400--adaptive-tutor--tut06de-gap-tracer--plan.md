# Plan: TUT-06D/E and essential capability-gap tracer

Date: 2026-07-18 14:00
Area: adaptive-tutor / capability-gap
Status: Approved after architecture corrections

## Goal

Close the reference tutor host with one optional OpenAI Responses decision
adapter and an offline demo, then implement the smallest dependency-correct
capability-gap tracer proving that an agent can report a missing capability to
a local operational registry. The tracer observes only; it cannot execute,
export, prioritize, install, or modify the harness.

## Scope

- In scope:
  - TUT-06D direct optional Responses adapter over `TutorDecisionPort`;
  - TUT-06E offline scripted demo, recorded Responses parity, adversarial
    closure, install/import gates, and honest setup/privacy documentation;
  - GAP-01 strict structured contracts, operational service/view/port, and
    dedicated SQLite registry;
  - GAP-02 separate host report manifest/service with a compact local receipt;
  - one offline vertical proof: unsupported capability -> structured report ->
    exact retry deduplication -> trusted local aggregate query.
- Out of scope:
  - Agents SDK, ChatGPT subscription/session reuse, OAuth/cookies, UI, CLI live
    workflow, new StudyTools/capabilities, provider-owned loop/state;
  - GAP-03+, workaround execution, outbox, Flywheel/devkit import, transport,
    GitHub, automatic proposal/promotion, or self-modification;
  - PDF/OCR/audio conversion and `sbobby-web`.

## Current OpenAI Preflight

- Official current model docs expose Responses and structured outputs for the
  configurable GPT-5.6 family; no model id is hard-coded by core behavior.
- Current Python SDK uses `AsyncOpenAI` and
  `client.responses.create(model=..., input=..., instructions=...,
  text={"format": {"type": "json_schema", ...}})`; `output_text` is the
  bounded structured response surface.
- The SDK retries connection failures, 408, 409, 429, and 5xx by default. The
  adapter must instantiate it with `max_retries=0`; `TutorHostRunner` remains
  the retry-budget owner.
- Only API-key mode is supported. ChatGPT subscription is not API authority.
- Streaming, background mode, provider tools, file search, and provider-managed
  conversation state are not used in this slice.
- Responses requests set `store=False`, SDK `max_retries=0`, and an explicit
  bounded `max_output_tokens`; the host retains no provider conversation state.

## Execution Order

1. TUT-06D: implement and verify the optional technical adapter.
2. TUT-06E: close parity/demo/docs only after D is green.
3. GAP-01: implement the local operational registry and strict contracts.
4. GAP-02: expose the separate agent-facing host report surface and vertical
   local-only tracer.
5. One aggregated correctness/security review over both lanes, approved fixes,
   full tests, Ruff, strict mypy, clean-wheel/import checks, build, commit/push.

## Architectural Invariants

- The runner is the only decision loop and capability gateway caller.
- The Responses adapter receives only `TutorHostContext`; it cannot import or
  receive gateway, authority, ingestion, filesystem, event, or store owners.
- Provider SDK imports are confined and optional. Base package import works
  without the SDK.
- GAP records contain closed structured values only and live in a dedicated
  operational SQLite plane. No course/session/learner event or StudyTool is
  added.
- The model cannot author trusted limitation/error receipts, identity,
  priority, severity, status, workaround outcome, or external destination.
- GAP-02 records but never executes. Its public result is compact and
  `local_only=true`.
- The GAP work is explicitly a partial essential tracer. GAP-01/02 remain open
  until their approved retention/rate/workaround/resolution surfaces ship.

## Risk Classification

- TUT-06D: high — provider adapter, public configuration, secrets, retries.
- TUT-06E: medium — additive demo/docs/evals over stable contracts.
- GAP-01: high — public contracts, canonical codec, persistence/schema.
- GAP-02: high — untrusted agent input crossing an operational write boundary.

## Verification

- Focused adapter/host, gap contract/store/service, architecture, and demo tests.
- Base import with SDK absent and recorded transport parity without network.
- Opt-in live smoke skipped unless SDK, key, and explicit model are configured.
- Exact seven StudyTools and capability discovery remain unchanged.
- `.venv/bin/ruff check src tests`.
- `MYPYPATH=src .venv/bin/mypy --strict src`.
- `PYTHONPATH=.:src .venv/bin/python -m pytest -q`.
- `uv build`; install/import wheel without extra; dependency metadata check for
  the `openai` extra; `git diff --check`.

## Review Economy

- One serialized Luna implementer per tightly coupled lane; reuse its context
  for the dependent bead.
- One aggregated reviewer after all four slices. A separate security reviewer
  is used only if the aggregated review identifies a security question it
  cannot resolve.
