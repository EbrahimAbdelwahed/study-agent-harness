# Task Bead: AML-05 manifest contract

Status: Complete
Priority: P1
Type: task
Depends On: AML-04

## Worker Profile

Use `implementer` for production, then `test-engineer`, `architecture-auditor`,
`security-reviewer`, and `reviewer` with non-overlapping file scopes.

## Context

The released host-operation vocabulary is agent-operable. Release 0.2 now needs
a pure desired-intent contract before any filesystem target, source snapshot,
planner, status, or apply behavior can be introduced.

## What To Do

- Move technical repository-config ownership out of CLI composition without
  changing its existing import contract or validation behavior.
- Implement strict frozen `LifecycleManifestV1` values, bounded parsing,
  canonical bytes, and a domain-separated SHA-256 fingerprint.
- Add one bounded no-follow reader for the explicitly selected manifest file;
  never open the declared repository or source paths.
- Register repository-free and network-free `manifest schema` and `manifest
  validate [PATH]` operations.
- Return only schema/version/fingerprint/count information from validation.

## Likely Files / Packages

- `src/study_agent/repository_config.py`
- `src/study_agent/lifecycle/`
- `src/study_agent/adapters/filesystem/lifecycle.py`
- `src/study_agent/cli/config.py`, `registry.py`, `commands.py`
- `tests/contract/lifecycle/`, `tests/contract/cli/`
- `tests/architecture/test_lifecycle_boundaries.py`

## Acceptance Criteria

- [x] Golden and reordered manifests have stable canonical bytes/fingerprint.
- [x] Every required field, type, count, string, path, date, config and arbitrary
      settings bound is enforced with one safe validation error class.
- [x] Duplicate keys/IDs, unknown fields, invalid UTF-8, non-finite numbers,
      secret-like settings and behavior/authority/executable vocabulary fail.
- [x] Validation does not open a repository, declared source, credential, model,
      index, run store, or network connection.
- [x] CLI discovery advertises both additive operations under
      `agent-operations@1` and the stable JSON envelope.
- [x] Lifecycle contracts do not reverse-import CLI/adapters/provider/stateful
      infrastructure and domain/event/projection packages do not import lifecycle.
- [x] Existing 64 KiB repository-config bound is enforced on serialization too.

## Verification

- Focused manifest/config/CLI/architecture tests
- `python -m pytest -q`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`
- `git diff --check`
- Python 3.12 and 3.13 CI matrix

## Out Of Scope

- Repository target resolution, declared source reads, source snapshots, plans,
  status, apply, receipts, lifecycle authority, events, deletion, remote sources,
  model calls, new StudyTools, provider branches, product or Sbobby changes.

## Notes / Handoff

- Fingerprint domain is `study-agent-lifecycle-manifest-v1\0` followed by the
  existing canonical JSON encoding.
- Course IDs are global; source IDs are unique within their course.
- Paths remain lexical manifest-relative strings in this slice.
