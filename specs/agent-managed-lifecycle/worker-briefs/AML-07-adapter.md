# Worker Brief: AML-07 filesystem source adapter

## Assignment

Implement the sole bounded source reader beneath one explicit trusted root.

## Allowed Files

- `src/study_agent/adapters/filesystem/source_input.py`
- `src/study_agent/adapters/filesystem/__init__.py`

## Invariants

- Open root/directories with `O_DIRECTORY|O_NOFOLLOW` and the leaf with
  `O_NOFOLLOW|O_NONBLOCK`.
- Compare device, inode, mode, link count, size, mtime and ctime before/after;
  rebind the complete path after capture.
- Accept only regular strict UTF-8 `.txt`/`.md` files.
- Enforce inclusive per-file, count and aggregate bounds before returning.
- Write no repository state and perform no model/network call.

## Gates

- Adversarial filesystem contract tests
- Ruff and strict mypy
- Security review
