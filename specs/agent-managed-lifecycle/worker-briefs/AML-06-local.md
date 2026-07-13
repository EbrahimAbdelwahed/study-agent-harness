# Worker Brief: AML-06 local implementation

## Allowed Production Files

- `src/study_agent/adapters/filesystem/repository_target.py`
- `src/study_agent/adapters/filesystem/__init__.py`
- `src/study_agent/cli/repository.py`
- mechanical compatibility exports in `src/study_agent/cli/__init__.py`

## Allowed Tests

- `tests/contract/filesystem/test_repository_target.py`
- focused updates in `tests/unit/cli/test_repository.py`
- `tests/architecture/test_lifecycle_boundaries.py`

## Invariants

- Use fd-relative open/mkdir/list/read/write/link/unlink/rmdir operations after
  the trusted root is opened; never call `mkdir(parents=True)` on a validated tail.
- Final symlinks and non-directories are rejected before mutation.
- `ResolvedRepositoryTarget` carries lexical tail plus verified root/parent identity,
  not study state or authority.
- Config publication is no-replace, fsynced and preceded/followed by target rebinding.
- Rollback removes only entries created by the attempted initialization.
- Portable fd-relative APIs cannot prevent a transient syscall through a directory
  renamed by an actor with parent rename authority; pre/post rebind plus exact-inode
  rollback must guarantee no escaped durable repository or publication remains.
- Preserve `LocalRepositoryError`, `LocalRepositoryPaths` and
  `initialize_local_repository` import compatibility from the CLI package.
- Do not touch source ingestion, domain/events, projections, model adapters,
  skills/playbooks, StudyTools or slice 07+.
