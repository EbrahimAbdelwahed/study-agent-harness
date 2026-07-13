# Review Report: Agent-managed lifecycle slice 04

Date: 2026-07-13
Reviewer: code-quality-governor and security reviewer

## Findings

- [P1, closed] The initial CI smoke did not execute the complete documented
  journey from the clean-installed wheel. Python 3.12 and 3.13 now run the real
  external-agent example, including offline tool invocation and two identical
  exports.
- [P2, closed] Extraction and the example needed stronger path and byte
  verification. Extraction now rejects final symlinks and non-regular files,
  checks stable file identity, and publishes with atomic no-replace semantics;
  the example hashes the extracted bytes and uses an absolute executable.
- [P2, closed] The packaged skill now states explicitly that procedural v0.1
  commands use only the authority of the local user who launched the agent.

## Required Fixes

- None remaining.

## Verification Commands

- `python -m pytest -q`: passed, 444 tests; one opt-in network smoke skipped.
- `python -m ruff check .`: passed.
- `.venv/bin/python -m mypy`: passed, 167 source files.
- `git diff --check`: passed.
- Skill creator `quick_validate.py`: passed.
- `python -m build --wheel --sdist --no-isolation`: wheel and sdist built.
- Clean virtual-environment wheel install, `describe`, extraction, offline
  StudyTool invocation and deterministic two-export example: passed.

## Architecture Notes

- The installed distribution is the sole owner of skill content, identity,
  version and fingerprint.
- The exact seven StudyTool contracts and fingerprints remain unchanged.
- The skill is a behavior and operating layer; adapters remain technical and
  the trusted embedding host remains the authority owner.
- The extraction command performs no repository, credential, model or network
  operation.

## Prompt / Eval Notes

- A blind unprimed agent completed the credential-free workflow and correctly
  skipped optional `ask` without a configured model. Its prerequisite, relative
  source-path and export-directory ambiguities were corrected and the evidence
  is preserved under the slice assets.

## Verdict

Approved after semantic and security re-review. No P0–P2 findings remain.
