# Log: OSS release candidate

Date: 2026-08-02 13:15 CEST
Area: release

## Summary

Prepared the contemporary `0.2.0` alpha core as a source release candidate.
The supported public boundary is the installed CLI plus the low-level
`study_agent.tools` contracts and registry. The current Knowledge Base, Build
Week archive, seven-tool compatibility surface, and sixteen owner-backed agent
operations were preserved.

The divergent historical release lane was used only as audit evidence. Its API
v1 and duplicate local runtime were rejected because they target the old core
and omit the contemporary operation-owner composition. Recall/FSRS, PDF
workarounds, browser/product shells, release publishing, and every downstream
product remain excluded.

Local commits:

- `07e8465 chore(release): prepare 0.2.0 source candidate`
- `c3a1b77 docs(release): isolate public candidate history`

## Files Changed

- `README.md`, `docs/integrations.md`: concise install, offline start,
  integration principles, limitations, and discovery pointers without copying
  the code-owned operation inventory.
- `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `SUPPORT.md`,
  `CONTRIBUTING.md`, `SECURITY.md`: aligned source-candidate and community
  policy for `0.2.0` alpha.
- `pyproject.toml`, `.gitignore`: completed generic package metadata and kept
  repository-local worktrees out of Git without deleting them.
- `src/study_agent/cli/main.py`: added human and JSON root-level version
  discovery while preserving `export --version` semantics.
- `.github/workflows/ci.yml`: added whitespace, required distribution-content,
  public-import, version, and clean-wheel regression gates; no publish workflow
  was added.
- `tests/quality/test_distribution_contents.py`: verifies wheel/sdist identity,
  required public assets, excluded local material, private paths/names, and
  high-confidence secret formats; CI cannot silently skip missing artifacts.
- `tests/architecture/test_oss_release_boundaries.py`: proves core public
  imports do not load rejected historical, UI, scheduling, or optional-provider
  modules.
- `tests/contract/cli/test_operator_skill_contract.py`: ignores retained
  worktrees and ordinary build caches while still rejecting a second main-tree
  operator skill.
- `specs/kb-v0-2/README.md`: records the single active admission-authenticity
  hardening reminder with its consumer-enforcement and forgery-test condition.
- Build Week/dev history: removed private local paths and downstream-product
  naming from the maintained candidate history without altering archived proof
  assets.

## Verification

- `PYTHONPATH=src .venv/bin/python -m pytest -q`: 2,157 passed, 3 skipped. The
  skips are the sandbox Unix-socket case and two opt-in network/provider smokes.
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 474 source files checked.
- Direct offline setuptools backend build with Python 3.13/setuptools 82.0.0:
  wheel and sdist built successfully as `0.2.0`. The local `.venv` lacks the
  `build` frontend; CI installs it explicitly and runs the equivalent PEP 517
  build on Python 3.12 and 3.13.
- `STUDY_AGENT_REQUIRE_DIST=1 PYTHONPATH=src .venv/bin/python -m pytest -q tests/quality`:
  4 passed against the rebuilt archives.
- Clean Python 3.13 wheel install with `--no-index`: passed `study-agent
  --version`, help, JSON demo, `agent-operations@2` discovery, operator-skill
  extraction, imports, and the external-agent example.
- Clean-wheel discovery: exactly seven compatibility tools and sixteen expanded
  manifests; recall reported only as `owner_unavailable`.
- Root `--version` before other global options: returned the version envelope
  and performed no repository operation; `export --version 2` integration test
  remained green.
- Release-document link validation: all relative links across nine maintained
  entry documents resolved.
- `git diff --check`: passed.
- `git -C .worktrees/kb08 status --short --branch`: clean after removing the
  ineffective five-line local experiment; the worktree itself remains present.
- Independent semantic review: clean after the root/subcommand version parsing
  fix.
- Independent security review: clean after artifact secret-content scanning,
  required CI archive mode, and explicit-path staging policy.

## Notes

- No push, tag, package upload, GitHub release, workflow dispatch, or other
  external action occurred.
- Pre-existing untracked duplicate specs, lockfile, KB audit, and repository log
  were preserved and deliberately excluded through explicit-path staging.
- Publication version selection, PyPI ownership/provenance, and broader platform
  support remain maintainer decisions outside this source candidate.
