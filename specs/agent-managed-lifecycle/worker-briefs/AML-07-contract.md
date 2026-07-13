# Worker Brief: AML-07 source snapshot contract

## Assignment

Add the provider-neutral immutable snapshot value and batch-capable source input
port. Do not open files or edit CLI composition.

## Allowed Files

- `src/study_agent/ports/source_input.py`
- `src/study_agent/ports/__init__.py`
- narrow bound-owner update in `src/study_agent/lifecycle/contracts.py`

## Invariants

- Snapshot identity is SHA-256 over the exact captured bytes.
- Paths are strict portable relative `.txt`/`.md` names.
- Limits are 16 MiB per file, 4,096 files and 512 MiB total.
- Values carry no principal, behavior, course, event or model authority.
- The port and values depend only on the standard library.

## Gates

- Focused contract tests
- Ruff and strict mypy
- `git diff --check`
