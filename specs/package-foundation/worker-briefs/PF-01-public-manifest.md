# Worker Brief: PF-01

## Assignment

Implement `PF-01` from `specs/package-foundation/slices/PF-01-public-manifest.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, `specs/package-foundation/slices/PF-01-public-manifest.md`, and `specs/package-foundation/beads/PF-01-public-manifest.md`
- existing root package, metadata, and public-contract tests

## Scope

You may change:

- `src/study_agent/__init__.py`
- `src/study_agent/api/__init__.py`, `api/manifest.py`, and the eight named `api/*.py` subfacade targets
- `tests/contract/test_public_manifest.py`, `tests/architecture/test_public_facade_boundaries.py`

Do not change:

- Package specs, slices, beads, briefs, `pyproject.toml`, domain behavior, adapters, storage, events, runtime behavior, CLI/UI, product modules, or dependencies

## Invariants and Requirements

- Implement exactly the frozen manifest fields and eight typed subfacade names; root exports only `__version__` and `api`.
- Freeze nested values, canonicalize JSON, and make the fingerprint stable across repeated calls and processes.
- Keep root import free of credentials, environment configuration, registration, files, databases, event loops, and optional modules.
- Prove every listed import with optional providers unavailable and reject unlisted public names.
- Preserve internal behavior and do not add dependencies or product references.

## Verification

Run:

```bash
uv run --python 3.12 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py
uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py
uv run --python 3.13 --extra dev python -c "import study_agent; print(study_agent.__version__); print(study_agent.api.public_manifest().fingerprint)"
git diff --check
```

## Report Back

Return:

- files changed;
- public import and manifest behavior implemented;
- exact verification results;
- profile constraints followed;
- unresolved questions;
- follow-up beads needed.
