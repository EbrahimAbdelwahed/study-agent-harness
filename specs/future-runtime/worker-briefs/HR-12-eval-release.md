# Worker Brief: HR-12

## Assignment

Implement `HR-12-eval-release` from `specs/future-runtime/slices/HR-12-eval-release.md`.

Worker target: Luna xhigh. Execute this final aggregate bead after HR-01 through HR-11.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-12-eval-release.md`
- `specs/future-runtime/beads/HR-12-eval-release.md`
- Prior release evidence from HR-05/07/09 and final workflow evidence from HR-11

## Scope

You may change:

- `tests/evals/runtime_release_report.py`
- `tests/evals/test_runtime_offline_release.py`
- `tests/evals/test_reviewer_macro_f1.py`
- `tests/evals/test_deterministic_replay.py`
- `tests/quality/test_future_runtime_distribution.py`
- Harness-owned release configuration/scripts only where an existing package convention explicitly permits them

Do not change:

- Runtime behavior, Cardine, product code, new dependencies, mandatory network/credentials, distributed JobStore, automatic model promotion, or paths outside eval/release configuration.

## Requirements

- Report separate schema/authority/citation/sealed-leak/coverage/unsupported-claim/reviewer-F1/replay and cost/token/latency fields.
- Shared RuntimeReleaseGate accepts only passing 1.1/1.2/1.3 evidence; HR-12 alone emits final 1.4.
- Build and clean-install wheel/sdist on Python 3.12/3.13 without `PYTHONPATH`; scan Cardine/provider/secret/entry-point leakage.
- Keep live Luna comparison explicitly marked and credentialed; offline verification remains complete.

## Acceptance Criteria

- Offline thresholds are 100% validity/coverage, zero unsupported claims, macro-F1 ≥0.95, deterministic replay, and no critical failures.
- Separate test/eval, semantic, and package/security review gates pass; live quality is within three percentage points only when explicitly enabled.
- Earlier slices cannot publish 1.4; HR-12 is the sole final aggregate publisher.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/evals/test_runtime_offline_release.py tests/evals/test_reviewer_macro_f1.py tests/evals/test_deterministic_replay.py tests/quality/test_future_runtime_distribution.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m build --wheel --sdist --outdir dist
git diff --check
```

Then clean-install both artifacts on Python 3.12 and 3.13 without `PYTHONPATH`; run live comparison only with an explicit marker and environment credential.

## Report Back

Return files changed, report/gate behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
