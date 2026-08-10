# PF-10 — Release

## Outcome

The foundation has a repeatable release gate that proves the built artifact,
public facade, offline behavior, dependency boundary, and PF-09 positive /
negative downstream-fixture co-install cycle on Python 3.12 and 3.13. PF-10
publishes only the exact `0.3.0` adoption release for Cardine to pin and
verify in its own adoption work; stable `1.0.0` promotion is PF-11 after CA-08
installed-parity evidence.

## Non-goals

- No implementation of future Job, worker, web-evidence, sealed-verification,
  or Decision Trace features.
- No Cardine release or product parity work; Cardine consumes this artifact
  through its own adoption spec after publication. Actual Cardine co-install
  and parity remain CA-04/CA-10-only.
- No live model/network requirement, remote telemetry default, or mandatory
  provider credential in the release path.

## Exact contracts

- Required release matrix: clean wheel/sdist install on Python 3.12 and 3.13;
  public import-manifest test; dependency-free base install; Ruff; strict
  mypy; full offline suite; reusable event/blob/replay/capability contract kit;
  no Cardine refs/product/auth/UI; successful PF-09 positive synthetic
  co-installation; and detection of the copied pre-adoption Cardine collision
  by the PF-09 negative fixture. Actual Cardine co-install parity belongs
  only to CA-04 and CA-10.
- Release CI builds once, stores the wheel and sdist as artifacts, and runs
  verification against those artifacts in clean environments. It never uses a
  sibling checkout, editable source path, or `PYTHONPATH` injection.
- Release checks compare `pyproject.toml`, `study_agent.__version__`, the
  public manifest package version, `README.md`, `CHANGELOG.md`, and license
  metadata. Mismatches fail the release.
- PF-10 publishes exactly `0.3.0`; Cardine pins that exact version during
  adoption. PF-11 alone may promote the facade to `1.0.0`, and only after
  signed/hashed CA-08 installed-parity evidence. After PF-11, MAJOR may break,
  MINOR adds compatible functionality, and PATCH contains compatible bug
  fixes. Every public facade change updates manifest and contract fixtures.
- Offline fixtures are a complete release path. Live provider comparisons are
  opt-in and cannot gate a base package install. Credentials are environment
  references only and never committed or serialized in release evidence.
- Release evidence records command, interpreter, artifact checksum, test
  result, and known pre-existing failure. A failed gate blocks the tag and
  leaves the local artifact available for diagnosis.

## Probable files

- `.github/workflows/ci.yml` and `.github/workflows/release.yml` — matrix,
  artifact-install, archive, and publish gates.
- `scripts/release/check_public_facade.py`,
  `scripts/release/check_distribution.py`, and
  `scripts/release/check_side_by_side.py` — deterministic release probes.
- `tests/quality/test_distribution_contents.py`,
  `tests/contract/test_public_manifest.py`, and the PF-04/PF-06 contract-kit
  suites — release evidence inputs.
- `CHANGELOG.md`, `README.md`, `SECURITY.md`, and release metadata — version
  and adoption instructions.
- `dev/logs/YYYY-MM-DD-HHMM--release--package-foundation--log.md` — factual
  command outcomes for the implementation pass.

## Dependencies

PF-01 through PF-09 are required. PF-10 is the `0.3.0` adoption gate and does
not add new public domain behavior. PF-11 is a separate stable-facade
promotion gate and is not part of this publication.

## Removal conditions

Remove temporary artifact-install shortcuts, local path assumptions, and
release-only compatibility probes after clean artifact CI is green. Keep only
the reusable public-manifest, archive, and side-by-side checks that protect the
published contract.

## Review surface

Review the release checklist, version transitions, artifact checksums, Python
matrix, offline/live boundary, and the exact Cardine pin instructions. Inspect
the wheel and sdist from the CI artifact rather than source checkout output.

## Exact verification

```text
git diff --check
uv run --python 3.12 --extra dev ruff check src tests
uv run --python 3.13 --extra dev ruff check src tests
uv run --python 3.12 --extra dev mypy
uv run --python 3.13 --extra dev mypy
uv run --python 3.12 --extra dev pytest -q
uv run --python 3.13 --extra dev pytest -q
uv build --out-dir /tmp/study-agent-harness-package-foundation-release
uv run --python 3.13 --extra dev python scripts/release/check_public_facade.py /tmp/study-agent-harness-package-foundation-release
uv run --python 3.13 --extra dev python scripts/release/check_distribution.py /tmp/study-agent-harness-package-foundation-release
uv run --python 3.13 --extra dev python scripts/release/check_side_by_side.py /tmp/study-agent-harness-package-foundation-release
```

`check_side_by_side.py` runs the PF-09 positive synthetic fixture and then
the copied pre-adoption negative fixture in clean environments for both
interpreters. It asserts successful positive installation and the expected
duplicate-package or entry-point failure for the negative fixture. It never
resolves a sibling checkout, imports Cardine, or runs a Cardine test; actual
Cardine co-install/parity is CA-04/CA-10-only.

The final report records Python versions, artifact names and SHA-256 hashes,
all command outcomes, the exact adoption version, and any unrelated pre-
existing failure without weakening a gate.

## Risks

- Source-checkout tests can hide packaging defects. Run every release probe
  against clean built artifacts.
- A version bump without manifest/test updates can silently break Cardine.
  Require metadata, facade, docs, and fixture agreement.
- Live model availability can make releases flaky. Keep live comparisons opt-in
  and report quality/cost/latency separately from offline gates.

## Definition of done

- All required matrix, lint, typing, offline, contract-kit, package, positive
  synthetic co-install, and negative-collision gates pass on Python 3.12 and
  3.13.
- Wheel/sdist checksums and metadata are recorded; no forbidden files or imports
  are present.
- Adoption pin is documented as the exact published `0.3.0`; PF-11 is named as
  the only `1.0.0` stability-promotion gate after CA-08 evidence.
- Release evidence is reproducible from a clean artifact environment and is
  recorded in the matching factual dev log.
