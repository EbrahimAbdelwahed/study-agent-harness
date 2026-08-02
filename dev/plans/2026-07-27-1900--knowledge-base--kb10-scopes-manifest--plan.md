# Plan: KB-10 scopes and corpus manifest

Date: 2026-07-27 19:00
Area: knowledge-base

## Goal

Add the canonical, event-authorized membership of sources in exam scopes and
the deterministic manifest an agent can inspect before retrieval planning.

## Scope

- In scope:
  - strict provider/model-neutral scope, policy, capability, and manifest
    contracts;
  - service-authorized add/remove membership events with deterministic event
    identity and replay reducers;
  - one source in many scopes without duplicating units;
  - explicit whole-corpus selection rather than an implicit missing scope;
  - a bounded manifest builder from canonical source/unit state plus explicitly
    supplied derived availability snapshots.
- Out of scope:
  - transport, tools, agent planning, tutoring state, retrieval ranking, index
    persistence, connector implementation, and model inference.

## Approach

1. Add `ScopeId` plus frozen scope-policy and manifest contracts with strict
   codecs, stable ordering, finite bounds, and no learner/workflow fields.
2. Add explicit scope-configuration and membership event codecs and reducers.
   Human and service principals may configure trusted scope policy and
   membership; model principals may not. Require the source to exist, reject
   unknown scopes/removals, make exact retries idempotent, and store only
   source IDs so canonical units are never copied. Policy replacement must
   name the exact previous policy version; same-version conflicting payloads
   and stale replacements fail closed.
3. Add a pure manifest builder which accepts either an explicit exam scope or
   the explicit whole-corpus selector, reads canonical source/unit state, and
   takes derived coverage/capability/conformance snapshots as bounded inputs.
4. Register the event schemas through the existing ingestion registry seam.
5. Pin codecs, authority, replay, multi-scope isolation, no-duplication,
   absent/present capability snapshots, and bounds with focused tests.

## Risks

- Membership is canonical event-sourced state; a permissive codec or ambiguous
  remove could make replay diverge.
- The manifest aggregates canonical and derived state. Its API must label
  availability honestly and must not turn derived counters into authority.
- Existing flashcard/exam “scope” types are unrelated execution artifacts and
  must not be reused or changed.

## Verification

- `pytest -q tests/unit/knowledge/test_scopes_manifest.py`
- `ruff check` on changed source and tests
- `mypy` on changed source and tests
- relevant knowledge and architecture tests after integration

## Review gate

Plan review completed by the orchestrator on 2026-07-27 with these binding
clarifications:

- Events are the only canonical mutation owner. A scope must be configured
  before membership can change, and policy replacement uses explicit
  compare-and-set against the previous version.
- Human/service authority is accepted for trusted configuration; model
  authority is rejected.
- Whole-corpus selection is a named value, never `None`, an empty string, or a
  fallback after an unknown scope.
- Source-class order/priors are policy data supplied by the owner (including
  D-17), never hardcoded ranking behavior.
- Manifest coverage, retrievers, adapters, conformance, and connector hints
  are explicitly labelled derived inputs. The builder may summarize them but
  may not turn them into canonical state or infer missing hints.
- Membership stores references only; units and source manifests are never
  copied into scope state.

After implementation, request independent correctness review and independent
focused tests before integration.
