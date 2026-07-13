# Slice 07: Safe source snapshots

Release: 0.2
Depends on: slices 05–06

## Contract unlocked

Validated source declarations resolve into immutable, checksummed byte snapshots
through one filesystem boundary shared by procedural and declarative ingestion.

## API seam

- `study_agent.ports.source_input`: immutable source snapshot protocol/value.
- `study_agent.adapters.filesystem.source_input`: the sole safe source reader,
  extracted from current CLI `source add` handling.
- `study_agent.adapters.filesystem.lifecycle`: manifest loading only; source
  reads delegate to the shared adapter.

Paths are relative to the manifest directory. Absolute paths, `.`, and `..` are
rejected. Every component is no-follow checked; only regular `.txt`/`.md` files
are accepted. Before/after checks compare device, inode, mode, link count, size,
`mtime_ns`, and `ctime_ns`; captured-byte checksum is the snapshot identity.

## Runnable checkpoint

Run traversal, symlink, replacement/growth, same-inode same-size overwrite,
non-regular, invalid UTF-8, per-file, count, and total-byte adversarial fixtures.

## Verification

- Existing procedural security tests pass through the shared adapter.
- Lifecycle and procedural callers receive identical bytes/checksums/errors.
- Boundaries are 16 MiB per file, 4,096 files, and 512 MiB total.
- Additional roots are trusted host options, never manifest content.
- Snapshot construction writes no repository state and makes no network call.

## Human review checkpoint

Security-review the source boundary. Remote/archive acquisition requires a
separate future adapter and ADR.
