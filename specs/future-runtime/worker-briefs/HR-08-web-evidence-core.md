# Worker Brief: HR-08

## Assignment

Implement `HR-08-web-evidence-core` from `specs/future-runtime/slices/HR-08-web-evidence-core.md`.

Worker target: Luna xhigh. Execute only this quarantined offline bead.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-08-web-evidence-core.md`
- `specs/future-runtime/beads/HR-08-web-evidence-core.md`
- Existing source/citation ports and adapter/test conventions

## Scope

You may change:

- `src/study_agent/ports/web_evidence.py`
- `src/study_agent/web_evidence/contracts.py`
- `src/study_agent/web_evidence/broker.py`
- `src/study_agent/web_evidence/scripted.py`
- `tests/unit/web_evidence/test_contracts.py`
- `tests/contract/web_evidence/test_connector.py`
- `tests/integration/test_scripted_web_evidence.py`
- `tests/adversarial/test_web_candidate_quarantine.py`
- `tests/adversarial/test_web_limits.py`

Do not change:

- Paths outside the allowlist, including admission, SourceRevision writes, live adapters, Cardine policy, credentials, arbitrary URL retrieval, and base dependencies.

## Requirements

- Keep scripted connector deterministic/offline and candidate output untrusted.
- Enforce 8 queries, 10 candidates/query, 45s timeout, 256 KiB candidate, HTTPS-only references, no cookies/credentials/active execution, and 7-day retention.
- Preserve provenance/hash/trust and explicit partial failures; broker cannot admit or write canonical state.
- Obtain separate test and semantic/security review gates before HR-09.

## Acceptance Criteria

- Contract, scripted, quarantine, and limit tests pass without network or credentials.
- Independent semantic and security reviews separately approve prompt-injection, credential, retention, and authority isolation.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/web_evidence/test_contracts.py tests/contract/web_evidence/test_connector.py tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py
.venv/bin/python -m ruff check src/study_agent/ports/web_evidence.py src/study_agent/web_evidence tests/unit/web_evidence tests/contract/web_evidence tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, web-boundary behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
