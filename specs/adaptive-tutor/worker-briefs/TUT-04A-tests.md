# Worker Brief: TUT-04A tests

## Goal

Independently pin the public identity, codec, provenance, profile-selection, and
agent-guidance contracts implemented by TUT-04A.

## Allowed Files

- `tests/unit/artifacts/test_content_contracts.py`
- `tests/unit/artifacts/test_identity_and_provenance.py`
- `tests/unit/pedagogy/test_profile_catalog.py`
- `tests/architecture/test_artifact_contract_boundaries.py`

## Forbidden Files

- All production files, other tests, docs/specs, adapters, tools, export/CLI,
  state/events/services, `sbobby-web`, and configuration.

## Acceptance Criteria

- Golden deterministic batch/artifact/revision identities prove candidate keys,
  timestamps, and credentials are not identity inputs.
- Each of four content kinds round-trips exact JSON and rejects every extra,
  unknown, malformed union, reserved lifecycle field, provider/credential, and
  Anki-shaped field/value.
- Assessment/study-brief negative fixtures pin the TUT-05/07 boundary.
- Provenance round-trips with observed technical model receipts but rejects
  missing/failed/duplicate validators, source/read dependency drift, selection
  mismatch, fingerprints, and secret-shaped fields. Flashcards require a
  matching closed-catalog selection receipt; non-flashcard artifacts forbid it.
- Human-authored provenance round-trips only with HUMAN plus an exact
  interaction and rejects every generated-only field; generated provenance
  cannot weaken its required proof fields.
- Verified media covers valid blob/source/verifier linkage and rejects filename,
  HTML, unverified, malformed digest, out-of-range source index, and secret
  receipt shapes.
- Catalog discovery is immutable/deterministic; default is hybrid; explicit
  morphology requires a trusted learner/material basis; MODEL/course-title/
  model-output selection is impossible by type or rejected.
- Descriptor assertions instruct an agent when to use hybrid vs morphology and
  expose tradeoffs without Anki/provider/runtime behavior.
- Architecture test pins imports and unchanged seven StudyTools/capabilities.

## Verification

- New test files, relevant existing contract tests, Ruff, strict mypy, and
  `git diff --check`.

## Report

Report concrete semantic mismatches as findings. Do not edit production, commit,
or delegate.
