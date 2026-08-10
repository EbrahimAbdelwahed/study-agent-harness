# Worker Brief: PF-09

## Assignment

Implement `PF-09` from `specs/package-foundation/slices/PF-09-distribution.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01/PF-06/PF-08/PF-09 slices, and `specs/package-foundation/beads/PF-09-distribution.md`
- current `pyproject.toml`, CI workflows, package metadata, archive tests, and fixture conventions

## Scope

You may change:

- `pyproject.toml`, root/API package files, `src/study_agent/py.typed`
- distribution quality/side-by-side tests and both named distribution fixtures
- `.github/workflows/ci.yml`, release workflow metadata, and version/license docs only for package alignment

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, product source/fixtures, migration/alias code, runtime dependencies, credentials, or PF-10 publication logic

## Invariants and Requirements

- Distribution is `study-agent-harness`, regular namespace is only `study_agent`, and base dependency list is empty.
- Optional integrations remain lazy and archives exclude tests, dev files, worktrees, secrets, absolute paths, and product material.
- Harness owns `study-agent*`; positive fixture owns only `cardine*` and `cardine`; copied pre-adoption fixture reports duplicate package or entry-point collision.
- Clean tests install built artifacts without editable paths, sibling checkouts, or `PYTHONPATH`; no test imports Cardine.

## Verification

Run:

```bash
export dist_dir=$(mktemp -d /tmp/study-agent-harness-distribution-check.XXXXXX)
uv build --out-dir "$dist_dir"
uv run --python 3.13 --extra dev pytest -q tests/quality/test_distribution_contents.py tests/contract/distribution/test_side_by_side_install.py
uv run --python 3.13 --extra dev python -c "import pathlib, zipfile, tarfile, os; root=pathlib.Path(os.environ['dist_dir']); whl=next(root.glob('*.whl')); sdist=next(root.glob('*.tar.gz')); zipfile.ZipFile(whl).testzip(); tarfile.open(sdist).getnames(); print(whl.name, sdist.name)"
git diff --check
```

## Report Back

Return files changed, metadata/namespace/archive/fixture behavior, exact
verification, profile constraints followed, unresolved questions, and follow-up beads.
