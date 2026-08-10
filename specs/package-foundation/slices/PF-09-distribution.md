# PF-09 — Distribution

## Outcome

The harness builds an installable wheel and sdist with a collision-free
namespace and explicit entry points. A clean environment can install the base
package without optional providers and run the complete co-install cycle: a
positive synthetic downstream fixture that owns only `cardine`, followed by a
copied pre-adoption Cardine fixture that must fail closed on the duplicate
`study_agent`/entry-point collision. Actual Cardine co-install is CA-04/CA-10-
only; PF-09 does not import or test the Cardine repository.

## Non-goals

- No Cardine package changes, source migration, CLI alias shim, or product
  entry-point implementation. Actual Cardine co-install/parity is not a PF-09
  test target.
- No dependency expansion in the base package and no vendored provider/runtime
  framework.
- No publication or credential rotation in this slice; PF-10 owns release
  evidence and publication gates.

## Exact contracts

- Distribution metadata remains `study-agent-harness`; regular top-level
  package remains exclusively `study_agent`. Cardine owns `cardine` and must
  not ship a second regular `study_agent` package after adoption.
- Root imports expose only the PF-01 facade/version. Internal modules,
  `src/study_agent` layout, and reference CLI/browser composition are not
  semver surfaces.
- Base `dependencies = []` in `pyproject.toml`. SQLite uses the standard
  library. Provider, FSRS, PDF, OpenTelemetry, and specialist integrations are
  optional extras/adapters with no import at base-install time.
- Harness owns `study-agent*` console script names. The positive fixture at
  `tests/fixtures/distribution/synthetic-downstream-positive/` exposes only
  `cardine*` names and owns only `cardine`. The negative fixture at
  `tests/fixtures/distribution/cardine-pre-adoption-negative/` copies the
  pre-adoption package/scripts and must detect the expected duplicate package
  or entry-point collision. Actual Cardine co-install success belongs only to
  CA-04 and CA-10; no Harness test imports Cardine.
- Package data includes only approved runtime assets such as `py.typed` and
  explicitly documented reference fixtures. Tests, `dev/`, worktrees, local
  paths, credentials, and private product material never enter the wheel or
  sdist.
- CI and integration tests install the built artifact into a clean temporary
  environment. They do not use sibling checkouts, editable installs, or
  `PYTHONPATH` injection to prove package behavior.
- The adoption release recommendation is `0.3.0`; Cardine pins the exact
  published version during migration. Internal modules may change without
  compatibility coverage as long as the public manifest and semver policy hold.

## Probable files

- `pyproject.toml` — package metadata, extras, scripts, package data, and
  Python matrix; changes are implementation work owned by this slice.
- `src/study_agent/__init__.py`, `src/study_agent/api/__init__.py`, and
  `src/study_agent/py.typed` — namespace/facade package data.
- `tests/quality/test_distribution_contents.py` and new
  `tests/contract/distribution/test_side_by_side_install.py` — the test must
  run both the positive and negative fixture in one clean-environment cycle.
- `tests/fixtures/distribution/synthetic-downstream-positive/` and
  `tests/fixtures/distribution/cardine-pre-adoption-negative/` — isolated
  fixture distributions; neither fixture is a Cardine source dependency.
- `.github/workflows/ci.yml` and release workflow files — artifact-install
  verification only, with no source-path shortcuts.
- `README.md`, `CHANGELOG.md`, `SECURITY.md`, and package metadata docs —
  version/license alignment where the release slice owns it.

## Dependencies

PF-01 defines the facade, PF-06 defines explicit capability registration, and
PF-08 defines the runtime import boundary. PF-10 consumes the built artifact
and release metadata.

## Removal conditions

Do not add a Harness-side workaround for the copied Cardine namespace. Remove
editable/sibling-checkout CI paths once artifact-install checks are green.
Cardine adoption owns removal of its duplicate package and aliases.

## Review surface

Review package file lists, metadata dependencies, console scripts, optional
extras, license/version text, and side-by-side install behavior. Inspect wheel
and sdist archives directly for tests, dev files, private names, absolute user
paths, secrets, or duplicate package roots.

## Exact verification

```text
export dist_dir=$(mktemp -d /tmp/study-agent-harness-distribution-check.XXXXXX)
uv build --out-dir "$dist_dir"
uv run --python 3.13 --extra dev pytest -q tests/quality/test_distribution_contents.py tests/contract/distribution/test_side_by_side_install.py
uv run --python 3.13 --extra dev python -c "import pathlib, zipfile, tarfile, os; root=pathlib.Path(os.environ['dist_dir']); whl=next(root.glob('*.whl')); sdist=next(root.glob('*.tar.gz')); zipfile.ZipFile(whl).testzip(); tarfile.open(sdist).getnames(); print(whl.name, sdist.name)"
git diff --check
```

The smoke installs the wheel and sdist separately in clean Python 3.12 and
3.13 environments, installs the positive synthetic fixture, and asserts
distinct top-level files/scripts and successful imports. In the same test
command, it attempts the copied pre-adoption negative fixture and asserts the
expected duplicate `study_agent` or console-script collision. The command
must not resolve a sibling checkout or import Cardine. Actual Cardine
co-install/parity is CA-04/CA-10-only.

## Risks

- Setuptools package discovery can include an unintended regular package.
  Assert archive file lists and import ownership in CI.
- Optional extras can become mandatory through eager imports. Test base install
  with provider modules unavailable.
- Existing local scripts may rely on legacy aliases. Preserve Harness names
  only; Cardine migration owns product alias removal.

## Definition of done

- Wheel and sdist metadata match the public facade, license, and version.
- Base install has no mandatory third-party dependency and imports without
  optional packages.
- Harness and the positive synthetic downstream fixture install side by side
  without collisions, and the copied pre-adoption collision is detected
  explicitly by the negative fixture.
- Archives exclude tests, dev/worktrees, secrets, absolute paths, and private
  product material.
- Focused archive, install, quality, and diff checks pass on the declared
  Python versions.
