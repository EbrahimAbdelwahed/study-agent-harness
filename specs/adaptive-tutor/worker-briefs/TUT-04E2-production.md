# Worker Brief: TUT-04E2 artifact replay and export v2

## Goal

Add exact artifact replay to local runtime/lifecycle composition and an explicit
deterministic export v2, while leaving export v1 bytes, file set, default CLI
behavior, and the seven public StudyTools unchanged.

## Allowed Files

- `src/study_agent/application/export.py`
- `src/study_agent/application/artifact_export.py`
- `src/study_agent/application/__init__.py`
- `src/study_agent/adapters/filesystem/export.py`
- `src/study_agent/adapters/filesystem/__init__.py`
- `src/study_agent/cli/commands.py`
- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/repository.py`
- `src/study_agent/adapters/sqlite/lifecycle_observer.py`

## Forbidden Files

- Artifact codecs/reducers, event schemas, tools/capabilities, model/provider
  adapters, migrations, provisional C1 files, specs/docs, tests, dependencies,
  configuration, and `sbobby-web`.

## Public Contract

- Preserve `EXPORT_SCHEMA_VERSION = 1`, existing `ExportBundle`, and exact
  behavior of `ExportService(events).assemble(course_id)`.
- Add closed `ExportVersion(V1="1", V2="2")`,
  `EXPORT_V2_SCHEMA_VERSION = 2`, strict `ExportBundleV2`, and keyword-only
  `version: ExportVersion = ExportVersion.V1` on `assemble`.
- CLI becomes `export COURSE_ID --output PATH [--version {1,2}]`, default `1`.
  Registry declaration/example and JSON receipt expose the exact chosen version.
- Before normal v1 allowlist decoding, detect exact members of
  `ARTIFACT_EVENT_TYPES`. V1 must raise exactly
  `ExportStateError("artifact export requires v2")`; unknown similarly prefixed
  event names retain the existing not-allowlisted failure.

## Replay and Artifact Rows

- V2 replays course, source-ingested/source-selected, session, study-context,
  and artifact events in one exact registry. Export is storage-neutral: register
  the existing strict source decoders with source reducers directly rather than
  using a blob-loader registration. Artifact replay validates source/chunk
  commitments. Materialize `ProjectionArtifactView` only after complete replay.
- Add `register_artifact_events` to normal CLI repository and lifecycle-observer
  registries. Old repositories replay unchanged; do not silently rebuild or
  migrate derived state.
- Cross-check every decoded proposal revision, decision, terminal status,
  supersession, batch and source linkage against the typed snapshot. Order v2
  artifact rows by proposal event course sequence then ordinal, never timestamp
  or hash identity. Wrap corrupt decoder/reducer/view failures in stable,
  non-secret `ExportStateError` messages.
- One exact `artifacts.jsonl` row per revision contains schema version 2,
  artifact/revision/batch/session identities, ordinal, kind, proposal origin,
  status, prior revision, parent artifact, canonical content, proposal proof,
  nullable decision, and positive-allowlisted provenance. No timestamps.
- `proposal_proof` is generated-only. Decision authority is `human` or
  `service_policy`; public policy retains only policy id/version/fingerprint and
  result fingerprint, never request id or internal inputs.
- Generated public provenance allowlists origin, run id, source commitments,
  read dependencies, public prompt identity/version/composition/layer
  fingerprints, retrieval identity/version/fingerprints, ordered validator
  identity/version/pass/disposition/result fingerprints, pins excluding model
  adapter, profile selection, output fingerprint, and prior revision. Human
  provenance allowlists origin, interaction id, source commitments, read
  dependencies, and prior revision. Build from typed values; never subtract keys
  from raw provenance JSON.
- Exclude principal ids, idempotency keys, raw prompt text, all model receipts and
  adapter/model/response/usage fields, policy request id, credentials, source
  bytes, paths/filenames, and unverified media. Canonical content may contain only
  already-validated `VerifiedMediaRef`; never load media bytes.

## Writer Compatibility

- V2 contains the exact v1-named files plus `artifacts.jsonl`. Container schema
  versions are 2 while nested artifact content retains schema version 1.
- Keep v1 file construction byte-for-byte in behavior. Add a separate typed v2
  construction path selected by exact bundle type; do not make schema version a
  mutable field on v1 `ExportBundle`.
- Manifest v2 checksums all six data files with the existing sorted
  name/hash/size algorithm. Files remain newline-terminated and publication stays
  atomic/no-replace.

## Verification

- Focused existing export/CLI/repository checks, Ruff, strict mypy,
  architecture/tool parity, and `git diff --check`.

## Report

Report exact API/CLI changes, v1 non-regression evidence, v2 file/row schema,
typed redaction allowlist, replay registrations, and commands. Do not edit tests,
specs/docs, commit, or delegate.
