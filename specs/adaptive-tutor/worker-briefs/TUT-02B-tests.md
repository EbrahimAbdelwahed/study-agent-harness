# Worker Brief: TUT-02B tests

## Goal

Independently pin the public TUT-02B snapshot behavior without changing
production.

## Allowed Files

- `tests/unit/tutor_snapshot/test_snapshot_values.py`
- `tests/contract/tutor_snapshot/test_snapshot_reader_contract.py`
- `tests/integration/test_tutor_snapshot_replay.py`

## Required Coverage

- Exactly one store read and one replay-derived high-water under a racing fake.
- Missing/known/conflicting states for all five statement kinds.
- Separate configured hints and exact divergence without precedence.
- Mixed learner, note, grounded-answer, and general-assistant timeline ordering
  with event evidence.
- Current revision selection after source revision changes.
- Strict fail-closed malformed ownership/linkage behavior.
- Canonical snapshot bytes identical across repeated rebuilds.
- Public local repository composition and absence of next-action/capability/
  provider/mastery fields.

## Verification

- One behavior at a time, then focused suite, Ruff, strict mypy, full offline
  pytest, and diff check.
