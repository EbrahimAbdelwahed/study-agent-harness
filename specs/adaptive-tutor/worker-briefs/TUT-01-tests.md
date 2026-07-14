# Worker Brief: TUT-01 tests

## Goal

Add independent behavior-first coverage for the fixed TUT-01 production
contract. Do not modify production files.

## Allowed Files

- `tests/unit/study_context/**`
- `tests/contract/study_context/**`
- `tests/integration/test_progressive_study_context.py`
- `tests/architecture/test_import_boundaries.py` only to add `study_context` to
  the existing core-package boundary

## Forbidden Files

- all production, docs, specs, existing tests, and configuration.

## Required Coverage

- strict values, codecs, envelope and unknown fields;
- empty view, additive statements, scalar conflict, explicit resolution,
  retraction, and preserved history;
- equal additive values retain separate provenance; later scalar conflicts
  reopen and retracting a selected winner does not resurrect superseded values;
- actor/course/origin ownership;
- identical retry, changed retry conflict, stale expected sequence and race;
- mixed course/session/context replay and byte identity;
- lifecycle observation and export-v1 compatibility with context events;
- unchanged public StudyTool fingerprints.
- `study_context` participates in the existing core import-boundary gate.

## Verification

- focused TUT-01 tests
- `.venv/bin/ruff check` on added tests
- `.venv/bin/mypy --strict` on added tests where supported
- `git diff --check`
