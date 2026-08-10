# Worker Brief: HR-01

## Assignment

Implement `HR-01-contract-firewall` from `specs/future-runtime/slices/HR-01-contract-firewall.md`.

Worker target: Luna xhigh. Execute only this bead; the orchestrator has already approved the contract boundary.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-01-contract-firewall.md`
- `specs/future-runtime/beads/HR-01-contract-firewall.md`
- Existing authority/error/serialization conventions under `src/study_agent/` and current focused test directories

## Scope

You may change:

- `src/study_agent/jobs/contracts.py`
- `src/study_agent/ports/jobs.py`
- `src/study_agent/runtime/policy_firewall.py`
- `src/study_agent/verification/contracts.py`
- `tests/unit/jobs/test_contracts.py`
- `tests/unit/verification/test_portable_refs.py`
- `tests/contract/jobs/test_golden_vectors.py`
- `tests/adversarial/test_runtime_policy_firewall.py`
- `tests/fixtures/jobs/**`
- `tests/fixtures/verification/**`

Do not change:

- Every source, test, fixture, config, or documentation path not listed above, including Cardine paths and `specs/future-runtime/README.md` or slice files.
- SQLite stores, executors, workers, web connectors, generators, UI, CLI, dependencies, and public behavior outside HR-01.

## Requirements

- Implement the exact sole lifecycle, fixed defaults, identity fingerprints, retry classes, opaque refs, authority allowlist, bounded children, and sealed-view deny-list from HR-01.
- Require the orchestrator-recorded PF-11 and CA-10 precondition before dispatch; do not import or reference Cardine in Harness code.
- Keep fixtures opaque and canonical; MODEL cannot approve/admit/release/commit, and generic views cannot contain sealed bytes or raw identity.
- Add adversarial coverage for changed bytes under one identity, unknown policy/retry fields, unbounded children, and sealed payloads.

## Acceptance Criteria

- Contract and adversarial tests pass with deterministic round-trips and golden defaults.
- Separate focused test and independent semantic/security review gates both pass.
- No persistence, worker, model, network, Cardine, or second lifecycle seam is added.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/jobs/test_contracts.py tests/unit/verification/test_portable_refs.py tests/contract/jobs/test_golden_vectors.py tests/adversarial/test_runtime_policy_firewall.py
.venv/bin/python -m ruff check src/study_agent/jobs src/study_agent/runtime src/study_agent/verification tests/unit/jobs tests/unit/verification tests/contract/jobs tests/adversarial/test_runtime_policy_firewall.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return:

- files changed;
- contract and rejection behavior implemented;
- exact verification results;
- profile and scope constraints followed;
- unresolved questions;
- follow-up beads needed.
