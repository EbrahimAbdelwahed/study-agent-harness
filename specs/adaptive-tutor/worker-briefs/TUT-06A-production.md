# Worker Brief: TUT-06A production

## Goal

Implement only the provider-neutral host context, decision, receipt, codec, and
decision-port contracts defined by TUT-06A. Do not implement the runner,
scripted adapter, file capture, or OpenAI integration.

## Worker Profile

Use `reference-tutor-host-worker`. Keep this worker limited to strict external
host contracts and deterministic redaction/composition.

## Allowed Files

- `src/study_agent/hosts/__init__.py`
- `src/study_agent/hosts/contracts.py`
- `src/study_agent/hosts/context.py`
- `src/study_agent/ports/tutor_host.py`
- `src/study_agent/ports/__init__.py`

## Forbidden Files

- Tests, domain/state/event owners, tutor-snapshot and learner-evidence
  projections, capability gateway/bindings/manifests, skills, playbooks,
  prompts, tools, workers, ingestion/source input, adapters, CLI, dependencies,
  docs/specs, OpenAI/agent SDK/provider code, UI, `sbobby-web`, and the seven
  StudyTools.

## Required Context

- ADR-0004, TUT-03 capability contracts/gateway, TUT-02B snapshot contracts,
  TUT-05E learner-evidence port, and TUT-06A.
- Existing strict JSON freeze/canonical fingerprint patterns and provider-
  selector rejection helpers.

## Required Contracts

- Define strict frozen host-only values for advertised capability descriptors,
  pending continuation descriptors, host-file descriptors, redacted host
  context, action/retry receipt, and the closed decision/result-independent
  union named by TUT-06A.
- Compose the context from already-built immutable views and gateway discovery;
  do not mutate or wrap projection state as a second source of truth.
- Preserve only the minimum exact learner-facing/tutor evidence needed for host
  choice. Hidden assessment answers/rubrics, raw source bytes, paths, internal
  prompts/traces, credentials, principal/grant/retry/provider configuration,
  and canonical write authority must be structurally absent.
- Validate start inputs against the exact advertised public manifest schema.
  Validate dialogue answers only against a host-supplied pending descriptor;
  do not carry full trusted continuation bytes in model-visible contracts.
- Add canonical JSON codecs and domain-separated fingerprints with exact field
  sets, deterministic ordering, bounded text/count/bytes, and secret/path/
  provider-authority rejection.
- Define `TutorDecisionPort` as a narrow async protocol accepting only redacted
  context plus host-issued interruption token and returning only a closed
  decision. It exposes no effect method.

## Acceptance Criteria

- No provider, adapter, SDK, gateway implementation, persistence, filesystem,
  or model-playbook object appears in the public host contracts.
- A decision cannot express authority, persistence, arbitrary tool calls, or an
  unadvertised capability.
- Context and receipt fingerprints are stable, exact, and change for every
  semantically committed field.
- No production behavior outside the allowed files changes.

## Verification

- `.venv/bin/ruff check <allowed production files>`
- `.venv/bin/mypy --strict <allowed production files>`
- Existing capability/snapshot/evidence/import-boundary tests.
- `git diff --check`

## Report

Report public types, exact JSON shapes, fingerprints, redaction choices, and
commands/results. Do not commit or delegate.
