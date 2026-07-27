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

## Semantic review closure

Applied only the approved KB-12 findings: the HIGH ladder-collapse ancestry
finding and the MEDIUM golden-ranking, permitted-input-permutation, branching
ladder, and diversity-cap regression-coverage findings.  Ladder ownership now
walks the full validated canonical `PARENT` ancestry, including unmatched
intermediates; a matched coarse ancestor is assigned once to the stable
canonical-identity-selected narrow descendant while matched siblings remain
distinct primaries.  The test helper preserves candidate input order instead
of silently sorting it.

## Verification

- `ruff check src/study_agent/retrieval tests/unit/retrieval`: passed.
- `/private/tmp/study-agent-kb/.venv/bin/mypy --strict src/study_agent/retrieval/fusion.py src/study_agent/retrieval/__init__.py`: passed.
- `PYTHONPATH=src /private/tmp/study-agent-kb/.venv/bin/pytest -q tests/unit/retrieval`: 21 passed.
