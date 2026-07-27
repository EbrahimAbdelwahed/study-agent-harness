# Log: KB-12 deterministic fusion pipeline

Date: 2026-07-28 04:00
Area: knowledge-base

## Summary

Implemented the provider-neutral KB-12 fusion seam.  The pure pipeline validates
the sealed KB-11 batch and an exact admitted unit catalog, computes weighted RRF
with one contribution per retriever, collapses parent ladders, records bounded
structural/source-class/review/uncertainty priors, applies deterministic source
and section caps, and adds bounded context attachments after ranking.  Empty
candidate lists return an explicit insufficient result; every result-list
retriever must have a positive policy weight, while skipped-only retrievers
need none.

## Files Changed

- `src/study_agent/retrieval/fusion.py`: immutable policy, prior receipt,
  evidence-group/result contracts, catalog admission, fusion, collapse,
  diversity, and expansion.
- `src/study_agent/retrieval/__init__.py`: public fusion exports.
- `tests/unit/retrieval/test_fusion.py`: golden, ladder, priors, cap,
  provenance, hostile-catalog, and permutation-stability coverage.
- `specs/kb-v0-2/beads/KB-12-fusion-pipeline.md`: implementation-complete
  status pending semantic review.

## Verification

- `ruff check src/study_agent/retrieval/fusion.py src/study_agent/retrieval/__init__.py tests/unit/retrieval/test_fusion.py`: passed.
- `PYTHONPATH=src pytest -q tests/unit/retrieval/test_fusion.py`: 8 passed.
- `.../study-agent-harness/.venv/bin/mypy --strict src/study_agent/retrieval/fusion.py src/study_agent/retrieval/__init__.py`: passed.

## Notes

- The isolated checkout does not contain `dev/index.md`; no index update was
  needed for this bounded implementation.
- Status intentionally remains implementation complete until semantic review.
