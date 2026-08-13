# Task Bead: PF-09 Distribution

Status: Open
Priority: P2
Type: task
Depends On: PF-01, PF-06, PF-08

## Outcome

The harness builds clean wheel and sdist artifacts with only `study_agent` as
its regular namespace, explicit `study-agent*` entry points, no base runtime
dependencies, and a positive synthetic `cardine` fixture that co-installs
while a copied pre-adoption fixture reports the expected collision.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- Exact PF-09 metadata, namespace, optional extras, fixture, archive, and artifact-install criteria in `specs/package-foundation/slices/PF-09-distribution.md`.
- README package boundary and positive/negative co-install clarification.

## Grilling Evidence

- Approved Package Foundation Contracts section of the 2026-08-09 harness approval handoff; `specs/package-foundation/slices/PF-09-distribution.md`.
- Decision state: approved.
- ADR/glossary changes: none.

## Worker Profile

reuse `python-oss-bootstrap-worker`

Rationale:

This is a Python distribution boundary task covering metadata, namespace
ownership, clean installation, and import isolation, matching the profile's
package gates.

## Context

Cardine adoption requires an artifact boundary, not a sibling checkout or
source-path test. Harness owns `study-agent*`; a synthetic downstream positive
fixture proves `cardine` ownership, while the copied pre-adoption fixture is a
deliberate collision detector until downstream migration removes its duplicate.

## Invariants

- Distribution is `study-agent-harness`; regular top-level package is exclusively `study_agent`; base dependencies are empty.
- Optional provider, FSRS, PDF, telemetry, and specialist integrations never import at base-install time.
- Wheel/sdist exclude tests, dev/worktrees, secrets, local paths, and private product files; package data is allowlisted.
- Harness owns `study-agent*`; positive fixture owns only `cardine*` and `cardine`; actual Cardine co-install is not tested here.
- Archive and smoke checks install built artifacts in clean environments without editable paths, sibling checkouts, or `PYTHONPATH` injection.

## What To Do

- Align `pyproject.toml`, package data, entry points, optional extras, root facade/version, and license/version docs.
- Add isolated positive and copied pre-adoption negative fixtures and a single side-by-side install test.
- Add archive-content and clean wheel/sdist install checks for Python 3.12 and 3.13.
- Remove any local source-path shortcut from CI/integration package checks.

## Likely Allowed Files / Packages

- `pyproject.toml`, `src/study_agent/__init__.py`, `src/study_agent/api/__init__.py`, `src/study_agent/py.typed`.
- `tests/quality/test_distribution_contents.py`, `tests/contract/distribution/test_side_by_side_install.py`.
- `tests/fixtures/distribution/synthetic-downstream-positive/**`, `cardine-pre-adoption-negative/**`.
- `.github/workflows/ci.yml`, release workflow metadata, `README.md`, `CHANGELOG.md`, `SECURITY.md` only where distribution alignment is required.

## Acceptance Criteria

- [ ] Wheel/sdist metadata, root version, manifest version, entry points, license, and package data agree.
- [ ] Base install has no mandatory third-party dependency and imports without optional provider packages.
- [ ] Archive lists exclude tests/dev/worktrees/secrets/absolute paths and contain only the approved regular namespace.
- [ ] Harness plus positive `cardine` fixture install and import successfully; copied pre-adoption fixture fails with expected duplicate package or entry-point collision.
- [ ] Tests use built artifacts in clean environments and never import Cardine or resolve a sibling checkout.

## Verification

- `export dist_dir=$(mktemp -d /tmp/study-agent-harness-distribution-check.XXXXXX); uv build --out-dir "$dist_dir"`: artifacts build.
- `uv run --python 3.13 --extra dev pytest -q tests/quality/test_distribution_contents.py tests/contract/distribution/test_side_by_side_install.py`: archive and co-install tests pass.
- `uv run --python 3.13 --extra dev python -c "import pathlib, zipfile, tarfile, os; root=pathlib.Path(os.environ['dist_dir']); whl=next(root.glob('*.whl')); sdist=next(root.glob('*.tar.gz')); zipfile.ZipFile(whl).testzip(); tarfile.open(sdist).getnames(); print(whl.name, sdist.name)"`: archives are readable.
- `git diff --check`: no whitespace errors.

## Out Of Scope

- Cardine source changes, migration, CLI alias shims, product entry points, publication, credential rotation, base dependency expansion, or Harness-side collision workarounds.

## Removal Conditions

- Remove editable/sibling-checkout artifact checks and local path shortcuts after clean artifact tests pass; retain reusable archive and collision assertions.

