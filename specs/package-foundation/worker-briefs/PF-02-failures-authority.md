# Worker Brief: PF-02

## Assignment

Implement `PF-02` from `specs/package-foundation/slices/PF-02-failures-authority.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01/PF-02 slices, and `specs/package-foundation/beads/PF-02-failures-authority.md`
- existing domain errors, authority/context values, harness application, and contract tests

## Scope

You may change:

- `src/study_agent/api/authority.py`
- `src/study_agent/domain/errors.py`, `domain/authority.py`, `src/study_agent/application/errors.py`, `src/study_agent/ports/authority.py`
- `tests/contract/test_public_failures.py`, `tests/contract/test_authority_context.py`, `tests/architecture/test_authority_boundaries.py`

Do not change:

- Package specs, slices, beads, briefs, event schemas, storage adapters, module registration, capability gateway, runtime, package metadata, CLI/UI, product modules, credentials, or dependencies

## Invariants and Requirements

- Keep exactly seven public failure subclasses: validation, stale, unauthorized, conflict, not found, unavailable dependency, and internal failure.
- Use the approved per-composition Host issuer plus distinct injected authority
  port. Context values are opaque/read-only/non-serializable, are bound by a
  private object-identity marker, and reject direct/replace/cross-issuer
  forgery; reject MODEL durable effects before schema or adapter access.
- Translate every legacy enum plus provider, SQLite, filesystem, and unknown
  exceptions into safe public values while retaining local causes only for
  diagnostics.
- Canonicalize command kind and input bytes; prove equal-key convergence, changed-input conflict, stale no-op, cooperative cancellation, and secret redaction.
- Bound sanitization to depth 8, 256 nodes, 64 container items, 1,024 UTF-8
  bytes per string, and 16 KiB details; use strict JSON and never leak partial
  credentials, cookies, prompts, chain-of-thought, or raw tracebacks.

## Verification

Run:

```bash
uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_failures.py tests/contract/test_authority_context.py tests/architecture/test_authority_boundaries.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_event_state_kernel.py tests/integration/test_capability_gateway_lifecycle.py
uv run --python 3.13 --extra dev ruff check src/study_agent/api src/study_agent/domain src/study_agent/application tests/contract tests/architecture
git diff --check
```

## Report Back

Return:

- files changed;
- failure and authority behavior implemented;
- exact verification results;
- profile constraints followed;
- unresolved questions;
- follow-up beads needed.
