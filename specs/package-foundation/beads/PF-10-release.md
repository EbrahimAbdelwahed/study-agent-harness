# Task Bead: PF-10 Release

Status: Open
Priority: P2
Type: task
Depends On: PF-01, PF-02, PF-03, PF-04, PF-05, PF-06, PF-07, PF-08, PF-09

## Outcome

A repeatable release gate builds once and verifies the artifact, facade,
dependency boundary, offline suite, contract kit, and PF-09 fixtures on Python
3.12 and 3.13, then publishes exactly `0.3.0` as the adoption pin.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-10 matrix, artifact-install, metadata, offline/live boundary, semver, evidence, and `0.3.0` criteria in `specs/package-foundation/slices/PF-10-release.md`.
- README release gate and adoption pin requirements.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-10-release.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `cli-release-test-worker`

Rationale:

The gate is an offline release and clean-install verification lane with
artifact checks, documentation alignment, and reproducible command evidence.

## Context

PF-09 proves distribution shape; this bead turns it into a reproducible
adoption release gate. CI must test the built artifact, not a source checkout,
and live provider comparisons remain opt-in diagnostics.

## Invariants

- Required matrix covers clean wheel/sdist installs on 3.12/3.13, manifest, dependency-free base, Ruff, strict mypy, offline suite, contract kit, PF-09 positive install, and negative collision.
- CI builds once and tests that artifact without editable installs, sibling checkouts, or `PYTHONPATH` injection.
- `pyproject.toml`, `study_agent.__version__`, manifest package version, README, CHANGELOG, and license metadata must agree.
- Publication is exactly `0.3.0`; live providers and credentials never gate base installation; stable promotion belongs to PF-11 after external evidence.
- Evidence records command, interpreter, artifact checksum, result, and known unrelated failures without weakening gates.

## What To Do

- Add deterministic release probes for facade, archive contents, side-by-side fixtures, hashes, and metadata.
- Update CI/release workflow to build once and run matrix checks against wheel/sdist artifacts.
- Align adoption release docs and exact `0.3.0` pin instructions.
- Record reproducible release evidence and fail nonzero on any required gate.

## Likely Allowed Files / Packages

- `.github/workflows/ci.yml`, `.github/workflows/release.yml`.
- `scripts/release/check_public_facade.py`, `check_distribution.py`, `check_side_by_side.py`.
- `tests/quality/test_distribution_contents.py`, `tests/contract/test_public_manifest.py`, PF-04/PF-06 contract suites.
- `CHANGELOG.md`, `README.md`, `SECURITY.md`, release metadata, and one matching factual `dev/logs/...package-foundation...` file.

## Acceptance Criteria

- [ ] All required matrix, lint, typing, offline, contract-kit, artifact, positive fixture, and negative collision gates pass on 3.12 and 3.13.
- [ ] Release probes inspect built wheel/sdist and report names, hashes, interpreter, command, result, and unrelated pre-existing failures.
- [ ] Version, manifest, docs, license, and metadata agree; adoption pin is exactly `0.3.0`.
- [ ] No Cardine import/product/auth/UI dependency, live credential requirement, source-path shortcut, or weakened gate exists.
- [ ] Failed gate blocks publication while leaving local artifact evidence available.

## Verification

- `git diff --check`: no whitespace errors.
- `uv run --python 3.12 --extra dev ruff check src tests` and `uv run --python 3.13 --extra dev ruff check src tests`: lint passes.
- `uv run --python 3.12 --extra dev mypy` and `uv run --python 3.13 --extra dev mypy`: strict typing passes.
- `uv run --python 3.12 --extra dev pytest -q` and `uv run --python 3.13 --extra dev pytest -q`: offline suites pass.
- `uv build --out-dir /tmp/study-agent-harness-package-foundation-release`: artifacts build.
- `uv run --python 3.13 --extra dev python scripts/release/check_public_facade.py /tmp/study-agent-harness-package-foundation-release`, `check_distribution.py ...`, and `check_side_by_side.py ...`: release probes pass.

## Out Of Scope

- Future runtime features, Cardine release/parity, live model requirement, remote telemetry, credential changes, and stable `1.0.0` promotion.

## Removal Conditions

- Remove temporary artifact-install shortcuts, local-path assumptions, and release-only compatibility probes once clean artifact CI is green; keep reusable release checks.

