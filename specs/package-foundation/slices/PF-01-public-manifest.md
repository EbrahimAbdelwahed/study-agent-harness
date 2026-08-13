# PF-01 — Public manifest

## Outcome

Downstream code can import a stable, typed `study_agent.api` facade and
inspect the exact public surface without importing implementation modules. The
root package exposes only the package version and facade entry point; optional
providers, adapters, UI, CLI, and filesystem code stay lazy and private.

## Non-goals

- No domain behavior, runtime composition, registration, or persistence change.
- No compatibility promise for internal `study_agent.*` modules.
- No Cardine import, product DTO, auth surface, or copied source mirror.
- No eager provider/model import and no new mandatory dependency.

## Exact contracts

- Distribution name remains `study-agent-harness`; regular package namespace
  remains `study_agent`.
- `study_agent.__version__` is a non-empty string equal to package metadata.
  The root module exports only `__version__` and `api` through `__all__`.
- `study_agent.api` exports an immutable `PublicManifest` value with:
  `facade_version`, `package_version`, `python_versions`, `subfacades`,
  `exports`, and `schema_versions`. All collections are tuples or immutable
  mappings and are canonically ordered.
- `facade_version` is an integer starting at `1`. `package_version` follows
  semantic versioning. During `0.x`, only names in `PublicManifest.exports`
  have compatibility coverage; internal modules have no guarantee.
- The manifest names exactly these typed subfacades: `runtime`, `authority`,
  `storage`, `sources`, `capabilities`, `artifacts`, `assessments`, and
  `recall`. A subfacade is importable without importing provider, UI, CLI,
  telemetry, or optional-extra modules.
- `public_manifest() -> PublicManifest` returns the same value on repeated
  calls. `manifest.to_json()` and `manifest.fingerprint` are deterministic.
- The import-manifest test imports every listed symbol from a clean base install
  and verifies that no unlisted symbol is presented as public. Importing the
  root package with model/provider modules made unavailable still succeeds.
- Root import does not read credentials, inspect environment configuration,
  register plugins, open files, create a database, or start an event loop.

## Probable files

- `src/study_agent/__init__.py` — reduce root exports to version and facade.
- `src/study_agent/api/__init__.py` — facade and manifest definition.
- `src/study_agent/api/manifest.py` — frozen manifest codec/fingerprint.
- `src/study_agent/api/{runtime,authority,storage,sources,capabilities,artifacts,assessments,recall}.py`
  — typed subfacade re-exports, added or populated by later slices.
- `tests/contract/test_public_manifest.py` — clean import and export allowlist.
- `tests/architecture/test_public_facade_boundaries.py` — eager import guard.

## Dependencies

None. PF-02 and later slices consume this manifest; PF-01 must not import
their implementation modules to make the manifest pass.

## Removal conditions

No temporary seam is required. Any compatibility re-export created while
moving existing symbols must be removed before PF-01 is accepted, or its
owning symbol must be listed in the manifest with a tested deprecation path.

## Review surface

Inspect `study_agent.__all__`, the manifest JSON/fingerprint, and the import
trace from a clean interpreter. Confirm that package version and facade version
are distinct, internal modules are absent from the public list, and optional
imports remain lazy. Confirm no product or private path text is present.

## Exact verification

```text
uv run --python 3.12 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py
uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_manifest.py tests/architecture/test_public_facade_boundaries.py
uv run --python 3.13 --extra dev python -c "import study_agent; print(study_agent.__version__); print(study_agent.api.public_manifest().fingerprint)"
git diff --check
```

The clean-base smoke must run with optional provider packages unavailable and
must not depend on a sibling checkout or `PYTHONPATH` override.

## Risks

- Existing callers may import internal symbols from the root. Preserve only
  approved facade exports and let the contract test expose accidental reliance.
- A broad `__init__` re-export can trigger provider or filesystem imports.
  Keep subfacades shallow and use explicit imports only.
- A mutable manifest can drift from code. Freeze all nested values and test a
  stable fingerprint.

## Definition of done

- `PublicManifest` and `public_manifest()` exist at the exact facade path.
- Root import exposes only version/facade and succeeds without optional extras.
- Every listed subfacade has a typed import target, even when its behavior lands
  in a later slice.
- Manifest serialization and fingerprint are deterministic and immutable.
- Focused 3.12/3.13 tests, architecture checks, and diff check pass.
- No code outside the PF-01 implementation scope is changed without a later
  slice owning it.
