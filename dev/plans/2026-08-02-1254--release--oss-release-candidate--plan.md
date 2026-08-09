# Plan: OSS release candidate

Date: 2026-08-02 12:54 CEST
Area: release

## Goal

Prepare the contemporary Study Agent Harness core as an installable, honest,
offline-verifiable OSS release candidate without importing the divergent legacy
release lane or any downstream product code.

## Scope

- In scope:
  - preserve the integrated Knowledge Base, Build Week archive, and public agent
    tool surface;
  - align package metadata and public version surfaces for the next alpha
    candidate;
  - keep the supported CLI and current `study_agent.tools` contracts as the
    public entry points, with conventional version discovery;
  - add distribution-content, clean-install, documentation, and CI gates around
    the package that actually exists;
  - refine the existing README candidate and add concise community/maintainer
    guidance;
  - remove current private-product naming from maintained release material and
    keep development-only material out of distributions;
  - remove the ineffective KB admission-seal experiment from `kb08` and record
    one public hardening reminder for the future consumer-enforced design.
- Out of scope:
  - the legacy `study_agent.api.v1` and duplicate local composition root;
  - recall/FSRS, PDF workarounds, browser/product shells, downstream products,
    or historical release-lane behavior;
  - push, tag, PyPI/GitHub release, protected-branch, or other external actions;
  - deleting or consolidating worktrees.

## Approach

1. Freeze the release boundary from read-only audits and architecture review.
2. Add focused package/CLI/test/CI hardening over the current owners and
   entrypoints; make worktree-local copies irrelevant to repository inventory
   tests instead of removing worktrees.
3. Update the README, version/security/community files, release checklist, and
   current public integration guide without duplicating command/tool inventories.
4. Remove only the five-line ineffective seal experiment from `kb08`, and add
   one deferred hardening item to the KB backlog.
5. Run focused tests, full pytest, Ruff, mypy, build wheel/sdist without network,
   inspect archives, and smoke-test the wheel in a clean environment.
6. Obtain independent semantic and security review, apply approved fixes, record
   exact verification, and create logical local commits.

## Risks

- The README already contains uncommitted work; edits must preserve its valid
  offline workflow and avoid reverting unrelated authorship.
- Version claims can drift across metadata, runtime, README, security policy,
  and changelog; a release-facing consistency test will pin them together.
- The old release lane contains attractive but stale API/runtime code that would
  silently drop the current 16-operation owner composition.
- Local worktrees contain packaged resources and currently confuse a repository
  scan; the test must distinguish the main checkout without masking real copies.

## Verification

- `PYTHONPATH=src .venv/bin/python -m pytest <focused release/tool/CLI tests>`
- `PYTHONPATH=src .venv/bin/python -m pytest -q`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy`
- `.venv/bin/python -m pip wheel --no-deps --no-build-isolation .`
- clean-wheel CLI, demo, describe, operator-skill, import, and external-agent smoke
- archive content inspection and `git diff --check`
