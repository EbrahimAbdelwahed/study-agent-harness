# Review Report: Agent-managed lifecycle slice 05

Date: 2026-07-13
Reviewers: architecture-auditor, code-quality-governor, security-reviewer

## Findings

- [P1, closed] The initial manifest reader could block while opening a FIFO.
  It now opens with `O_NONBLOCK|O_NOFOLLOW`, rejects non-regular files, and
  binds the stable descriptor identity back to the selected path.
- [P1, closed] Model settings needed complete explicit rejection for the
  approved authority, behavior, executable and deletion vocabulary. The values
  remain inert bounded JSON; only a trusted registered technical adapter may
  consume them, so no provider-key allowlist or model-specific branch entered
  lifecycle contracts.
- [P2, closed] Text/path validation now rejects control/format/surrogate code
  points, schemes/colons, Windows device names and trailing dot/space components.
- [P2, closed] Direct reader tests now cover flags, symlink, directory, FIFO,
  oversize, content mutation and path-replacement races.
- [P2, closed] Dormant source-size constants were removed from lifecycle; the
  active procedural reader remains their sole owner until slice 07.

## Required Fixes

- None remaining.

## Verification Commands

- `python -m pytest -q`: passed, 556 tests; one opt-in network smoke skipped.
- `python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 174 source files.
- `git diff --check`: passed.
- Golden fixture canonical length: 417 bytes.
- Golden fixture fingerprint:
  `bdcc1337312ed868c4db1859fdcfe3a7ee4093ba96539e38421bdb69bf30f1d7`.

## Architecture Notes

- `study_agent.repository_config` is the sole technical repository-config owner;
  `study_agent.cli.config` preserves import identity as a compatibility facade.
- `study_agent.lifecycle.contracts` owns only immutable desired intent,
  canonicalization, fingerprint and structural schema.
- The filesystem adapter reads one explicit manifest and never opens declared
  repository/source paths, credentials, models, indexes or network connections.
- Event state, projections and the exact seven StudyTools are unchanged.

## Prompt / Eval Notes

- No prompt, skill, playbook, RAG behavior or model invocation changed.

## Verdict

Approved after architecture, semantic and security re-review. No P0–P2
findings remain.
