# Worker Brief: TUT-04E2 artifact replay and export v2 tests

## Goal

Independently pin artifact-aware replay, deterministic export v2, fail-closed v1,
privacy, and exact v1 compatibility.

## Allowed Files

- `tests/contract/export/test_artifact_export_v2.py`
- `tests/integration/test_artifact_repository_replay.py`
- narrowly required assertions in
  `tests/contract/export/test_deterministic_export.py`
- narrowly required assertions in
  `tests/integration/test_reference_cli_independent.py`
- one narrowly relevant CLI registration/architecture test when an exact
  argument snapshot requires it

## Acceptance Criteria

- Existing pre-artifact API/CLI defaults to v1 and produces the historical six
  files byte-for-byte; repeated bytes and manifest hash match the pre-change
  golden behavior.
- Artifact stream plus default/explicit v1 fails exactly with
  `artifact export requires v2`; unknown/corrupt non-allowlisted schemas retain
  fail-closed behavior.
- Generated and human proposed/accepted/rejected/revised/superseded histories
  export twice byte-identically through v2. Parent/prior lineage, source
  commitments, profile selection, public prompt/retrieval/validator/pin
  fingerprints, generated proof, and public policy receipt survive JSON parsing.
- Artifact rows follow proposal sequence plus ordinal; every terminal revision
  has exactly one matching decision. Broken source commitment, orphan session,
  corrupt content/provenance/schema, duplicate terminal decision, and invalid
  supersession fail closed.
- All exported files exclude principal ids, idempotency keys, raw prompt text,
  model adapter/id/response/usage, policy request id, credential/secret fixtures,
  paths, filenames, source bytes, and unverified media. Verified media metadata
  may survive only through strict canonical artifact content.
- Old repository lifecycle observation remains compatible. Artifact repository
  opens, verifies, observes, and exports without canonical rewrite. Seven public
  StudyTools and their identities remain unchanged.

## Verification

- Focused contract/integration tests, full offline pytest, Ruff, strict mypy,
  architecture/tool parity, and `git diff --check`.

## Report

Report production mismatches only; do not edit production, specs/docs, commit,
or delegate.
