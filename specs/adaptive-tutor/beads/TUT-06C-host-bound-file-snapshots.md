# Task Bead: TUT-06C host-bound file snapshots

Status: Done
Priority: P0
Type: expand
Depends On: TUT-06A

## Outcome

Every local text or Markdown upload is captured as immutable trusted-host bytes
and bound to course/session plus an opaque file identity before any decision
adapter can observe a descriptor, content, role proposal, or ingestion action.

## Acceptance Criteria

- [x] Reuse `SourceInputPort` and `FilesystemSourceInput`; retain the existing
  strict UTF-8, direct relative `.txt`/`.md`, non-symlink, per-file, count, and
  aggregate byte limits. PDF/OCR/audio support is out of scope.
- [x] `HostFileSnapshot` binds an opaque host-generated file id, exact course
  and session, sanitized display name/media kind, byte size, SHA-256, and exact
  captured bytes. Changed bytes require a new snapshot identity.
- [x] The decision context contains only an ordered descriptor with opaque id,
  display name, media kind, size, and checksum. It never contains a local
  relative/absolute path or filesystem identity.
- [x] File bytes become model-visible only after a trusted lookup verifies the
  exact course/session/id/checksum binding. Source bytes are explicitly
  untrusted content, never host instructions.
- [x] The trusted host alone may request ingestion by exact opaque reference and
  chooses source id, title, trust/role authorization, expected event sequence,
  execution context, and whether to call `TextIngestionService`. The closed
  model decision contract cannot propose ingestion or source authority.
- [x] Snapshot storage is operational and bounded; it emits no canonical event,
  does not replace immutable source ingestion, and is not exported as course or
  learner evidence.
- [x] Repeated exact capture/lookup is deterministic. Missing, changed,
  cross-course/session, expired, forged, path-injected, oversized, or malformed
  snapshots fail before decision-provider or ingestion effects.

## Verification

- File-capture contract tests; descriptor redaction; changed-file and symlink
  races; cross-owner/expiry/tamper fixtures; ingestion bridge integration;
  existing filesystem source-input gates; Ruff; strict mypy.

## Plan Review Decisions

- This bead owns capture, descriptor projection, trusted lookup, and an explicit
  trusted-host ingestion bridge only. It does not add ingestion/file-role to the
  closed `TutorDecision` union, capability manifests, or StudyTools.
- File identity is issued by a trusted injected port; the model cannot supply
  ids. Exact retry is stable and changed bytes require a distinct id.
- Expiry uses injected `ClockPort` plus trusted positive TTL. Storage is bounded
  operational canonical bytes with no eviction and no course event.
- Configured count is capped by `MAX_HOST_FILES`; aggregate bytes are capped by
  `MAX_TOTAL_SOURCE_BYTES`. The local store lives in the explicit memory-adapter
  module named by the worker brief.
- `SourceInputPort`/`FilesystemSourceInput` remain the only filesystem/race
  owners; host code never opens or resolves a path.

## Worker Brief

- [Production and focused tests](../worker-briefs/TUT-06C-production.md)
