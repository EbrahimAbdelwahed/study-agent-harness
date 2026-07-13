# Task Bead: AML-06 safe repository target

Status: Complete
Priority: P1
Type: task
Depends On: AML-05

## Context

The manifest path is now structurally safe but repository initialization still
uses path-based `exists`/`mkdir(parents=True)` checks in CLI composition. That
check-then-resolve sequence can follow replaced or symlinked components.

## What To Do

- Introduce the sole fd-relative repository target resolver/initializer.
- Move repository path/layout/error ownership out of CLI composition while
  keeping existing procedural imports compatible.
- Resolve every existing component with `O_DIRECTORY|O_NOFOLLOW`.
- Create only beneath a verified directory descriptor and rebind parent/target
  identity before config publication.
- Preserve lock, fsync, recovery, idempotency, config-conflict and rollback behavior.

## Acceptance Criteria

- [x] Nested initialization succeeds through one resolved target contract.
- [x] Resolution writes nothing and rejects absolute manifest paths, dot/parent,
      symlinked intermediate/final components and non-directory components.
- [x] Parent/target replacement cannot leave or publish a repository outside the
      verified tree; exact-inode rollback removes mutations detected after a race.
- [x] Procedural init consumes the same resolver/initializer.
- [x] Compatible existing repository is a noop; config mismatch conflicts.
- [x] Concurrent initializers converge and interrupted owned layout recovers.
- [x] No source reads, lifecycle planning/apply, domain state or model calls land.

## Verification

- Focused target/CLI tests and race fixtures
- `python -m pytest -q`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`
- `git diff --check`
- architecture, semantic and security review

## Out Of Scope

- Source input/snapshots, plan/status/apply, extra roots from manifest content,
  deletion, remote paths, events, StudyTools, product or Sbobby changes.
