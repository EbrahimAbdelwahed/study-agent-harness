# Log: PF-09 distribution

Date: 2026-08-12 04:45
Area: harness distribution

## Summary

Added artifact-first wheel/sdist verification, a synthetic `cardine`-only
downstream fixture, and a deliberate pre-adoption collision fixture. Version
remains `0.2.0`; PF-10 owns the adoption release bump and publication gate.

## Files Changed

- `tests/contract/distribution/test_side_by_side_install.py`: archive ownership,
  clean install, entry-point, sdist rebuild, and collision checks.
- `tests/fixtures/distribution/**`: positive and negative isolated distributions.
- `tests/quality/test_distribution_contents.py`: explicit artifact directory.
- `.github/workflows/ci.yml`: run the PF-09 artifact test against the built dist.

## Verification

- Python 3.12.12: 6 focused distribution tests passed.
- Python 3.13.12: 6 focused distribution tests passed.
- Focused Ruff and strict mypy: passed.
- `git diff --check`: passed.

## Notes

- Wheel and sdist were built once at `/tmp/study-agent-harness-pf09-dist`.
- Clean install commands clear `PYTHONPATH` and do not use editable or sibling
  installations.
- The negative fixture is rejected structurally before an installer can
  overwrite the Harness-owned `study_agent` package or `study-agent*` scripts.
