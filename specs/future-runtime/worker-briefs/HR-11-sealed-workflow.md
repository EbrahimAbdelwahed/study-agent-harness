# Worker Brief: HR-11

## Assignment

Implement `HR-11-sealed-workflow` from `specs/future-runtime/slices/HR-11-sealed-workflow.md`.

Worker target: Luna xhigh. Execute only this generation/review/presentation bead after HR-10.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-11-sealed-workflow.md`
- `specs/future-runtime/beads/HR-11-sealed-workflow.md`
- HR-03 executor, HR-04 trace, HR-05 JobRuntime, HR-10 sealed contracts, and PF-05 SourceRevisionRef

## Scope

You may change:

- `src/study_agent/verification/workflow.py`
- `src/study_agent/verification/reviewer.py`
- `src/study_agent/verification/release.py`
- `src/study_agent/verification/presentation.py`
- `tests/integration/test_synthetic_verification_workflow.py`
- `tests/integration/test_verification_targeted_regeneration.py`
- `tests/integration/test_verification_presentation_receipt.py`
- `tests/adversarial/test_verification_authority.py`
- `tests/adversarial/test_sealed_content_leaks.py`

Do not change:

- Paths outside the allowlist, including HR-08/09 web modules, Cardine attempts/grades/contests, learner-model computation, generator self-review/release, and package release ownership.

## Requirements

- Start only with approved profile plus accepted plan; run generation child Jobs, independent CoverageReviewer, deterministic release, and progressive safe presentation.
- Block missing/partial/uncertain coverage and unsupported claims; apply novelty/drift targeted regeneration, two-failure suspension, version pins, and historical attempts.
- Validate HR-10 grant tuple before sealed reads; same-key commands converge, changed bytes conflict, and no raw identity/secret/question/answer crosses the host port.
- Keep separate test, reviewer, and security gates; HR-12 alone publishes final 1.4.

## Acceptance Criteria

- Workflow, targeted-regeneration, presentation, authority, and leak tests pass with reviewer independence and no content exposure.
- Separate focused tests, independent reviewer, and independent security review all pass; no release publication occurs in HR-11.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py
.venv/bin/python -m ruff check src/study_agent/verification tests/integration/test_synthetic_verification_workflow.py tests/integration/test_verification_targeted_regeneration.py tests/integration/test_verification_presentation_receipt.py tests/adversarial/test_verification_authority.py tests/adversarial/test_sealed_content_leaks.py
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, workflow/review/presentation behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
