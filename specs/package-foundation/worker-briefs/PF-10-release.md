# Worker Brief: PF-10

## Assignment

Implement `PF-10` from `specs/package-foundation/slices/PF-10-release.md`.

## Read First

- `AGENTS.md`, `CONTEXT.md`, and `CONTEXT-MAP.md`
- 2026-08-09 harness approval handoff, Approved Package Foundation Contracts section
- `specs/package-foundation/README.md`, PF-01 through PF-10 slices, and `specs/package-foundation/beads/PF-10-release.md`
- current CI/release workflows, metadata, artifact checks, contract suites, and documentation conventions

## Scope

You may change:

- `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- `scripts/release/check_public_facade.py`, `check_distribution.py`, `check_side_by_side.py`
- release quality/manifest/contract tests named by PF-10
- `CHANGELOG.md`, `README.md`, `SECURITY.md`, release metadata, and one factual package-foundation release log

Do not change:

- Package specs, slices, beads, briefs, future-runtime files, product release/parity files, runtime/domain behavior outside release checks, live-provider requirements, credentials, or stable promotion logic

## Invariants and Requirements

- Matrix covers clean 3.12/3.13 wheel/sdist installs, public manifest, dependency-free base, Ruff, strict mypy, full offline suite, contract kit, PF-09 positive install, and negative collision detection.
- CI builds once and verifies that artifact; no editable install, sibling checkout, or `PYTHONPATH` injection is allowed.
- Metadata, root version, manifest package version, README, CHANGELOG, and license values agree; publication version is exactly `0.3.0`.
- Live comparisons are opt-in diagnostics; credentials are environment references only; failed gates block publication and preserve artifacts/evidence.
- Evidence records exact command, interpreter, artifact checksum, result, and unrelated pre-existing failure without weakening a required gate.

## Verification

Run:

```bash
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

## Report Back

Return files changed, release matrix/probes/metadata/pin/evidence behavior,
exact verification, profile constraints followed, unresolved questions, and follow-up beads.
