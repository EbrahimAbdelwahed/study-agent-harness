# Task Bead: AML-07 safe source snapshots

Status: Complete
Priority: P1
Type: task
Depends On: AML-06

## Context

Procedural source ingestion still opens files through a CLI-private reader. The
declarative lifecycle needs the same captured bytes without creating a second
reader or trusting a path after it has been replaced.

## What To Do

- Introduce the provider-neutral immutable source snapshot port/value.
- Extract the sole bounded no-follow reader into the filesystem adapter.
- Rebind the complete root, directory and leaf identity after capture.
- Enforce 16 MiB per file, 4,096 files and 512 MiB aggregate bounds.
- Move procedural source ingestion to the shared snapshot owner and delete the
  CLI-private reader.

## Acceptance Criteria

- [x] Snapshot bytes, size and SHA-256 identity cannot disagree.
- [x] Traversal, symlink, non-regular, replacement/growth and invalid UTF-8
      inputs fail without repository writes or network calls.
- [x] Procedural and future declarative callers consume the same adapter bytes.
- [x] Batch count and aggregate byte bounds have one owner.
- [x] The CLI contains no second source reader or compatibility shim.
- [x] No lifecycle plan/apply, domain event, model or product behavior lands.

## Verification

- Focused port, adapter, CLI and architecture tests
- `python -m pytest -q`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`
- `git diff --check`
- architecture, semantic and security review

## Out Of Scope

Plan/status/apply, source acquisition, archive/URL/command inputs, deletion,
model calls, StudyTool changes, product UI and Sbobby Web.
