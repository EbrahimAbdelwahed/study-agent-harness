# Log: OSS PR readiness

Date: 2026-08-02 13:33 CEST
Area: release

## Summary

Audited open PR #7 against the repository's configured `main` default branch,
corrected its reproducible Linux SQLite failure, and resolved its divergent
history without importing excluded legacy capabilities into the audited OSS
candidate tree.

The failed GitHub Actions run was CI #79 (`30745538234`) for head
`1d1db0cd5670c0f62cdf45177ee25e97911e8aeb`. Both Python 3.12 and 3.13 jobs
failed the same contract test while auditing deliberately forged FTS DDL:
Ubuntu SQLite raised `OperationalError("error in tokenizer constructor")` from
`PRAGMA table_info` before the adapter reached its stable
`LexicalIndexIntegrityError` classification. This was a real cross-platform
regression, not an archive, worktree, checkout, dependency-install, or runner
failure.

The branch was 40 commits ahead and 52 behind `main`. A read-only merge-tree
simulation identified 22 conflicts: `README.md`, sixteen add/add KB spec files,
four KB source export/projection files, and the KB architecture test. The 52
main-only commits also contain recall/FSRS, browser/product shell, and PDF
workaround behavior that the approved release plan explicitly excludes. A
normal merge would therefore have made the tree mergeable by invalidating the
candidate boundary.

Commit `df4d901` records `origin/main` as the second parent with Git's `ours`
strategy, retaining the already audited candidate tree. As a result, `main` is
now an ancestor, merge-tree reports no conflicts, and the PR diff explicitly
removes excluded legacy surfaces instead of silently unioning them into the
release candidate.

## Files Changed

- `src/study_agent/adapters/sqlite/lexical_surfaces.py`: validate exact FTS DDL
  before asking SQLite to introspect virtual-table columns, preserving the
  stable integrity-error contract without catching unrelated operational
  database failures.
- `dev/plans/2026-08-02-1326--release--oss-pr-readiness--plan.md`: records the
  narrow CI and integration strategy and its explicit exclusions.
- This log: records remote evidence, conflict policy, and verification.

Local commits before this log:

- `9963780 fix(kb): classify malformed FTS schema portably`
- `df4d901 merge(main): preserve audited OSS release boundary`
- `a8f4a07 docs(release): keep PR audit product-neutral`

## Verification

- GitHub Actions job `python (3.12)` (`91490380972`): one failure, 2,155
  passes, four intended skips; exact failure was the forged-tokenizer contract.
- GitHub Actions job `python (3.13)` (`91490380909`): same exact failure, 2,155
  passes, four intended skips; no distinct environment failure.
- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/contract/retrieval/test_sqlite_lexical_surfaces.py`:
  13 passed.
- `STUDY_AGENT_REQUIRE_DIST=1 PYTHONPATH=src .venv/bin/python -m pytest -q`:
  2,157 passed, three intended skips.
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 474 source files checked.
- Direct offline setuptools build with Python 3.13/setuptools 82.0.0: rebuilt
  wheel and sdist successfully.
- `STUDY_AGENT_REQUIRE_DIST=1 PYTHONPATH=src .venv/bin/python -m pytest -q tests/quality/test_distribution_contents.py`:
  4 passed.
- Clean-wheel import, version, help, demo, describe, operator-skill extraction
  and resource identity, root-version regression, and external-agent smoke:
  passed.
- `git merge-tree --write-tree --messages HEAD origin/main`: passed without
  conflicts after the tree-preserving merge.
- `git merge-base --is-ancestor origin/main HEAD`: passed.
- Independent semantic review: clean; confirmed the SQLite classification,
  first-parent tree identity of the merge, and exclusion of unrelated files.
- Tracked-tree private-product-name search: no matches.
- `git diff --check` and explicit-path staging audits: passed.

## Notes

- The contemporary Knowledge Base, Build Week archive, and public tool surface
  remain unchanged except for the portable SQLite validation order.
- Five pre-existing untracked files remain unmodified and excluded.
- No PR metadata, merge, tag, release, or package publication was performed.
- The corrected remote CI run must be observed after pushing the final log.
