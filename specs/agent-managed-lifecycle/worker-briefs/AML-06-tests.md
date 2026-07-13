# Worker Brief: AML-06 tests

## Assignment

After production is stable, independently test the fd-relative repository target
contract. Do not edit production or invoke Claude/Anthropic tooling.

## Allowed Files

- `tests/contract/filesystem/test_repository_target.py`
- focused updates in `tests/unit/cli/test_repository.py`
- `tests/architecture/test_lifecycle_boundaries.py`

## Required Coverage

- Resolve is write-free; nested absent/existing targets retain lexical path and
  verified identities.
- Reject absolute manifest tails, empty/dot/parent/backslash, symlinked
  intermediate/final, file/FIFO components and incompatible roots.
- Nested initialization, compatible noop, config mismatch, nonempty collision,
  concurrent convergence and interrupted known-layout recovery.
- Inject replacement before mkdir, before publication and after publication;
  assert no escaped durable config/layout remains.
- Directly pin `O_NOFOLLOW|O_DIRECTORY`, fd-relative mutations, no `os.replace`,
  no-replace link publication and fsync order.
- Rollback removes only exact inodes created by the attempt and preserves raced
  or unknown entries.
- Existing `study_agent.cli` import/API behavior remains identical and procedural
  init delegates to the adapter owner.
- Architecture guards forbid CLI/lifecycle/domain/service/model/network imports
  from the target adapter and forbid a second initializer in CLI composition.

## Gates

- Focused pytest
- Full pytest where practical
- Ruff and strict mypy on allowed tests
- `git diff --check`
