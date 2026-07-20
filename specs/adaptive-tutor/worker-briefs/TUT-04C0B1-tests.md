# Worker Brief: TUT-04C0B1 isolated worker tests

## Goal

Independently prove fresh-context child-run isolation, strict receipts/views,
and exact retry without testing a provider-specific subagent implementation.

## Allowed Files

- `tests/unit/workers/test_worker_contracts.py`
- `tests/unit/workers/test_worker_service.py`
- `tests/architecture/test_worker_isolation_boundaries.py`

## Acceptance Criteria

- Valid tasks use the injected isolated-capability-run port with only the
  allowlisted task payload and a deterministically derived fresh child context.
  A recording port proves no tutor history, sibling output, unrelated material,
  credentials, principal/session fields, provider selector, or caller-supplied
  messages enter task/capability inputs, prompts, or model metadata; trusted
  authority remains only in the child `ExecutionContext` required by the gateway.
- Unknown/extra/secret-shaped recursive fields, arbitrary messages/history,
  malformed canonical summaries, forged pins/fingerprints, oversized payloads,
  and non-canonical bytes fail before child-run delegation.
- Task fixtures pin capability/manifest, complete pins, definition, output-schema
  fingerprint, and ordered expected validation step/source/id/version receipts;
  any observed mismatch fails closed before verified detail is exposed. Tests also
  pin typed validator disposition, exact task inputs in continuations/verified runs,
  and stable child run identity across every resume generation.
- Completed detail is derived only from a typed child observation carrying the
  exact verified run, manifest/output-schema proof, actual pins/definition,
  prompt receipt, and ordered passing validator/fallback provenance.
  Invalid/failed/cancelled/stale/tampered observations never expose detail, and
  B1 never invokes model/validator ports itself.
- Pending restart, at least two consecutive suspend/resume generations, response
  claims, terminal retry, changed task/pins/authority, and CAS races pin the
  repeatable state machine. Recovery may
  call the child port again but always reuses one deterministic child run and one
  playbook-owned model effect; terminal retries do not delegate.
- Direct pending completion/failure, running observations, resume-claimed crash
  recovery with the stored response, and stale-generation rejection are pinned.
- Compact view contains no raw output or private model data. Authorized detail
  view contains only verified structured output and public receipt provenance;
  another authority cannot read it.
- Codec tests pin canonical-byte equality, the five domain-separated
  fingerprints, canonical terminal-state receipt binding, structural forbidden-key
  recursion including camelCase aliases, sanitized machine failure codes, and exact
  128/64/32/16/256/512 KiB bounds without rejecting innocent natural-language strings.
- Architecture tests forbid provider SDKs, adapters, artifact/state owners,
  tutor sessions/history, direct model/validator imports, raw dispatcher
  callbacks, and StudyTool registration in the worker package.

## Verification

- Focused pytest, Ruff, strict mypy, relevant architecture/tool parity, and
  `git diff --check`.

## Report

Report production mismatches only; do not edit production, commit, or delegate.
