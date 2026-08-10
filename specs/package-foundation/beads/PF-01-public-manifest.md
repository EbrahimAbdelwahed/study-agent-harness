# Task Bead: PF-01 Public manifest

Status: Open
Priority: P1
Type: task
Depends On: none

## Outcome

An installed harness exposes one typed `study_agent.api` facade and immutable
`PublicManifest`. Root import exposes only `__version__` and `api`, succeeds
without optional modules, and has no provider, model, UI, CLI, or filesystem
side effects.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-01 outcome and contracts in `specs/package-foundation/slices/PF-01-public-manifest.md`.
- Public facade, deterministic fingerprint, lazy imports, and package-version alignment in `specs/package-foundation/README.md`.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/README.md` is marked Approved.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `python-oss-bootstrap-worker`

Rationale:

This is a recurring Python package-boundary task with clean-import and
metadata checks; the existing profile covers isolated package surfaces without
adding dependencies or broad behavior.

## Context

The package needs a machine-readable facade before later slices publish their
typed subfacades. The manifest must account for the exact public names while
keeping internal modules free to evolve and optional imports lazy.

## Invariants

- `study_agent.__all__` contains only `__version__` and `api`.
- Manifest collections are immutable, canonically ordered, and fingerprinted from deterministic JSON.
- Root import reads no credentials or environment configuration and performs no registration, file, database, or event-loop work.
- The eight named subfacades import without provider, model, UI, CLI, filesystem, telemetry, FSRS, or other optional modules.

## What To Do

- Implement frozen `PublicManifest`, deterministic `to_json()`, and a stable fingerprint.
- Publish the runtime, authority, storage, sources, capabilities, artifacts, assessments, and recall subfacade targets.
- Reduce root exports to version and facade while preserving lazy optional imports.
- Add clean-import, allowlist, immutability, and package-version contract tests.

## Likely Allowed Files / Packages

- `src/study_agent/__init__.py`: root export boundary.
- `src/study_agent/api/__init__.py`, `src/study_agent/api/manifest.py`: facade and manifest codec.
- `src/study_agent/api/runtime.py`, `authority.py`, `storage.py`, `sources.py`, `capabilities.py`, `artifacts.py`, `assessments.py`, `recall.py`: typed targets.
- `tests/contract/test_public_manifest.py`, `tests/architecture/test_public_facade_boundaries.py`: focused tests.

## Acceptance Criteria

- [ ] `PublicManifest` has frozen facade/package/python, subfacade, export, and schema-version fields with canonical ordering.
- [ ] `public_manifest()` returns the same immutable value and fingerprint on repeated calls; JSON output is byte-stable.
- [ ] Root and every listed subfacade import with optional modules unavailable and expose no unlisted implementation names.
- [ ] Import tracing proves no provider/model/UI/CLI/filesystem/telemetry import or side effect occurs at root import.
- [ ] Package metadata and `study_agent.__version__` are equal and non-empty.

## Verification

- `uv run --python 3.12 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py`: focused tests pass.
- `uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py`: focused tests pass.
- `uv run --python 3.13 --extra dev python -c "import study_agent; print(study_agent.__version__); print(study_agent.api.public_manifest().fingerprint)"`: clean import succeeds.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Event, authority, storage, source, capability, artifact, assessment, recall, runtime, distribution, or release behavior owned by later PF slices.
- Product modules, auth, UI, CLI changes, new dependencies, internal-module compatibility promises, or Cardine references.

## Removal Conditions

- Remove temporary root re-exports unless each name is listed and covered by the manifest contract.
- Do not retain a second manifest or an eager optional-import path after the tests pass.
