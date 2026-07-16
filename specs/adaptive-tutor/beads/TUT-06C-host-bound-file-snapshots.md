# Task Bead: TUT-06C host-bound file snapshots

Status: Blocked on TUT-06A
Priority: P0
Type: expand
Depends On: TUT-06A

## Outcome

Every local text or Markdown upload is captured as immutable trusted-host bytes
and bound to course/session plus an opaque file identity before any decision
adapter can observe a descriptor, content, role proposal, or ingestion action.

## Acceptance Criteria

- [ ] Reuse `SourceInputPort` and `FilesystemSourceInput`; retain the existing
  strict UTF-8, direct relative `.txt`/`.md`, non-symlink, per-file, count, and
  aggregate byte limits. PDF/OCR/audio support is out of scope.
- [ ] `HostFileSnapshot` binds an opaque host-generated file id, exact course
  and session, sanitized display name/media kind, byte size, SHA-256, and exact
  captured bytes. Changed bytes require a new snapshot identity.
- [ ] The decision context contains only an ordered descriptor with opaque id,
  display name, media kind, size, and checksum. It never contains a local
  relative/absolute path or filesystem identity.
- [ ] File bytes become model-visible only after a trusted lookup verifies the
  exact course/session/id/checksum binding. Source bytes are explicitly
  untrusted content, never host instructions.
- [ ] A model may propose a bounded source role or ingestion request referencing
  only the opaque id. The trusted host alone chooses source id, title,
  trust/role authorization, expected event sequence, execution context, and
  whether to call `TextIngestionService`.
- [ ] Snapshot storage is operational and bounded; it emits no canonical event,
  does not replace immutable source ingestion, and is not exported as course or
  learner evidence.
- [ ] Repeated exact capture/lookup is deterministic. Missing, changed,
  cross-course/session, expired, forged, path-injected, oversized, or malformed
  snapshots fail before decision-provider or ingestion effects.

## Verification

- File-capture contract tests; descriptor redaction; changed-file and symlink
  races; cross-owner/expiry/tamper fixtures; ingestion bridge integration;
  existing filesystem source-input gates; Ruff; strict mypy.
