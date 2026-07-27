# Log: KB-06 structural unitizer

Date: 2026-07-27 16:30
Area: knowledge base

## Summary

Implemented the deterministic KB-06 structural unitizer and granularity
ladder. The unitizer consumes a canonical UTF-8 substrate and real
`RevisionBinding`, emits document/section/passage occurrences, preserves
paragraph and atomic-region boundaries, and owns final `UnitId` derivation.
Structure-poor documents retain the exact 1,200-character v0.1 window fallback.
Versioned policies produce a complete conservative citation remap report with
explicit unmatched entries and no guessed replacements. KB-05 admission,
projection, and decoding now accept an explicit unitizer-version context, so
versioned rows are admitted only with matching caller-supplied policy.

## Files Changed

- `src/study_agent/knowledge/unitizer.py`: policy, identity-free drafts,
  deterministic unitization, atomic boundary handling, and remap report.
- `src/study_agent/knowledge/units.py`: explicit caller-supplied
  `unitizer_version` context for identity admission, reduction, and decoding.
- `src/study_agent/knowledge/__init__.py`: public unitizer exports.
- `tests/unit/knowledge/test_unitizer.py`: focused ladder, boundary, Unicode,
  fallback, determinism, binding, atomicity, and remap coverage.
- `specs/kb-v0-2/beads/KB-06-structural-unitizer.md`: marked KB-06 complete.
- `dev/plans/2026-07-27-1600--knowledge-base--kb06-structural-unitizer--plan.md`:
  implementation plan.

## Verification

- `PYTHONPATH=.:src pytest -q tests/unit/knowledge/test_unitizer.py`: 16 passed.
- `PYTHONPATH=.:src pytest -q tests/unit/knowledge tests/architecture/test_knowledge_boundaries.py`:
  341 passed.
- `ruff check .`: passed.
- `/private/tmp/study-agent-kb/.venv/bin/mypy --strict` on changed
  source/tests: passed with no issues.
- `python -m compileall -q src tests/unit/knowledge/test_unitizer.py`: passed.
- `PYTHONPATH=.:src pytest -q`: 641 passed, 2 skipped before an unrelated
  sandbox `PermissionError` in the browser integration test that binds a local
  TCP socket.

## Notes

- The thin `unitize_document` alias was removed; `unitize` is the sole public
  unitization entry point.
- No connectors, models, indexes, fragments, or dependencies were added.
