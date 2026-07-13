# Task Bead: trusted-run-receipts Expose trusted retrieval, validator, and recovered-run receipts

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260711-oss-harness-v01-batch6`
Spec: `docs/specs/oss-harness-v0-1-event-sourced-sessions-and-provenance.md`

## Worker Profile

create `run-receipt-worker`

Rationale:

No reusable specialization selected yet.

## Context

Answer persistence cannot honestly assemble provenance until retrieval/index metadata, validator execution, and completed run state are available through provider-neutral trusted records.

## What To Do

- Extend retrieval result/envelope with strategy/version/index/read-set receipt fields and populate them in SQLite FTS.
- Record trusted validator ID/version/disposition/result fingerprints in engine traces, including fallback validation.
- Add verified read-only completed/terminated-success run recovery from RunStore using exact definition, inputs, pins, and read dependencies.
- Reject corrupt/inconsistent checkpoint status, traces, inputs, pins, and dependency versions without re-executing effects.
- Add unit/contract/integration tests and preserve compatibility of existing generic playbooks.

## Likely Files / Packages

- `src/study_agent/ports/retrieval.py`, retrieval envelope, and SQLite FTS adapter: provider-neutral receipts
- `src/study_agent/playbooks/{contracts,runtime,engine}.py`: validator trace details and verified recovery
- relevant package exports
- `tests/contract/retrieval`, `tests/unit/playbooks`, and `tests/integration/test_playbook_engine.py`: receipt/recovery coverage

## Acceptance Criteria

- [ ] Retrieval provenance is explicit and never hardcoded by session/application code.
- [ ] Validator identities/outcomes come from registered executors and canonical result fingerprints.
- [ ] Recovered results are immutable, fully verified, and never rerun external steps.
- [ ] Only completed or semantically successful deterministic termination is recoverable for finalization.
- [ ] Existing retrieval and playbook behavior remains provider-neutral and offline.

## Verification

- `.venv/bin/python -m pytest tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/ports/retrieval.py src/study_agent/retrieval src/study_agent/adapters/sqlite/fts_retrieval.py src/study_agent/playbooks tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy src/study_agent/ports/retrieval.py src/study_agent/retrieval src/study_agent/adapters/sqlite/fts_retrieval.py src/study_agent/playbooks tests/contract/retrieval tests/unit/playbooks tests/integration/test_playbook_engine.py`: expected to pass or produce documented output

## Out Of Scope

- Session event schemas, application finalization, retrying external work, public tools, CLI, and provider branches.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
