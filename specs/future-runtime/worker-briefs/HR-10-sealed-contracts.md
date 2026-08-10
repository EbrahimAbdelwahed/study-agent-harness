# Worker Brief: HR-10

## Assignment

Implement `HR-10-sealed-contracts` from `specs/future-runtime/slices/HR-10-sealed-contracts.md`.

Worker target: Luna xhigh. Execute only this sealed-contract/leak-oracle bead; it has no web dependency.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-10-sealed-contracts.md`
- `specs/future-runtime/beads/HR-10-sealed-contracts.md`
- PF-05 generic SourceRevisionRef contract, HR-01 authority values, and current serialization conventions

## Scope

You may change:

- `src/study_agent/verification/contracts.py`
- `src/study_agent/verification/store.py`
- `src/study_agent/verification/views.py`
- `src/study_agent/verification/novelty.py`
- `src/study_agent/verification/presentation.py`
- `src/study_agent/ports/presentation_authority.py`
- `tests/unit/verification/test_contracts.py`
- `tests/unit/verification/test_novelty.py`
- `tests/contract/verification/test_serialization.py`
- `tests/contract/verification/test_presentation_grants.py`
- `tests/adversarial/test_sealed_content_leaks.py`

Do not change:

- Paths outside the allowlist, including HR-08/09 web modules, generators, Cardine approval, attempts/grades/contests, encryption claims, and dependencies.

## Requirements

- Implement versioned refs/pins, novelty thresholds, safe views, PresentationGrant tuple, injected validation port, and idempotent reveal/answer/finalize commands.
- Keep raw answer text host-resolved; reject sealed markers, raw identity, secrets, and credentials in every generic path and unknown kind.
- Make leak oracle scan nested list/search/export/trace/error/log/grant/presentation structures and fail closed.
- Obtain separate focused test, semantic, and security review gates before HR-11.

## Acceptance Criteria

- Serialization and novelty vectors pass; grant validation precedes sealed reads and changed idempotency bytes fail closed.
- Leak oracle passes every listed generic view/command and generation remains unavailable.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/unit/verification/test_contracts.py tests/unit/verification/test_novelty.py tests/contract/verification/test_serialization.py tests/contract/verification/test_presentation_grants.py tests/adversarial/test_sealed_content_leaks.py
.venv/bin/python -m ruff check src/study_agent/verification src/study_agent/ports/presentation_authority.py tests/unit/verification tests/contract/verification tests/adversarial/test_sealed_content_leaks.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, sealed contract/leak behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
