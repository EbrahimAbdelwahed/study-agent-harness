# Log: KB-10 scopes and corpus manifest

Date: 2026-07-27 16:36
Area: knowledge-base

## Summary

Implemented event-authorized scope configuration and source membership, strict
versioned scope policies, and a deterministic bounded corpus manifest. Scope
state stores source references only; the manifest reads canonical source/unit
state and explicitly supplied derived availability snapshots.

## Files Changed

- `src/study_agent/domain/identifiers.py`: added `ScopeId` and deterministic
  scope-event identity.
- `src/study_agent/domain/scopes.py`: added immutable scope policy, explicit
  whole-corpus selection, manifest source/snapshot contracts, bounded
  availability/conformance values, and deterministic serialization.
- `src/study_agent/domain/__init__.py`: exported the new domain contracts.
- `src/study_agent/knowledge/scopes.py`: added strict scope event codecs,
  human/service authority checks, CAS policy replacement, idempotent replay
  reducers, and the canonical-state manifest builder.
- `src/study_agent/knowledge/__init__.py`: exported scope event/manifest APIs.
- `src/study_agent/ingestion/projection.py`: registered scope event schemas at
  the existing source projection registry seam.
- `tests/unit/knowledge/test_scopes_manifest.py`: codec, authority, CAS,
  replay, multi-scope, no-duplication, snapshot, provenance, and determinism
  coverage.
- `specs/kb-v0-2/beads/KB-10-scopes-manifest.md`: marked acceptance criteria
  complete.

## Verification

- `pytest -q tests/unit/knowledge/test_scopes_manifest.py`: 7 passed.
- `pytest -q tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py tests/architecture/test_import_boundaries.py tests/integration/test_source_projection_replay.py`: 339 passed.
- `ruff check` on changed source and tests: clean.
- strict `mypy` on changed source and tests: clean (7 files).
- `pytest -q`: 2151 passed, 13 skipped, 1 failed. The failure is the
  pre-existing sandbox restriction preventing the browser-surface integration
  test from binding a localhost socket (`PermissionError: [Errno 1]`).

## Notes

- Source metadata is read from canonical top-level source rows when present or
  from the current revision manifest used by the repository's source
  projection; no units are copied into scope state.
- No retrieval, planner, transport, connector implementation, model inference,
  or dependency changes were made.
