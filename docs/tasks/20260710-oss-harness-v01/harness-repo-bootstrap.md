# Task Bead: harness-repo-bootstrap Bootstrap the isolated Python OSS package

Status: Completed
Priority: P1
Type: task
Depends On: none
Run ID: `20260710-oss-harness-v01`
Spec: `docs/specs/oss-study-agent-harness-v0-1.md`

## Worker Profile

create `python-oss-bootstrap-worker`

Rationale:

No reusable specialization selected yet.

## Context

The approved v0.1 architecture needs a clean Python 3.12+ distribution with enforceable dependency boundaries before domain code is added.

## What To Do

- Create the src-layout package, test layout, contributor commands, and minimal public metadata.
- Configure pytest, mypy strict mode, Ruff, and an import-boundary test that keeps provider/runtime/storage implementations out of domain and ports.
- Keep runtime dependencies empty unless a concrete first-slice requirement justifies one.

## Likely Files / Packages

- `pyproject.toml`: package metadata and development tooling
- `README.md`: contributor-oriented project boundary and commands
- `src/study_agent/`: package skeleton only
- `tests/architecture/`: import-boundary checks
- `.gitignore`: local Python artifacts

## Acceptance Criteria

- [x] A clean Python 3.12 environment can install the distribution.
- [x] The package imports with no provider SDK, Tau, web framework, or retrieval framework installed.
- [x] Formatting, typing, unit-test, and architecture commands are documented and runnable.
- [x] No Sbobby or existing workspace application is imported or modified.

## Verification

- `python3 -m pytest`: expected to pass or produce documented output
- `python3 -m mypy src`: expected to pass or produce documented output
- `python3 -m ruff check .`: expected to pass or produce documented output

## Out Of Scope

- Domain entities, persistence behavior, model adapters, RAG, CLI commands, and release publication.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
