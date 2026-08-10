# Task Bead: hr-12-eval-release Offline evaluation and runtime release gates

Status: Open
Priority: P1
Type: task
Depends On: hr-01-contract-firewall, hr-02-job-store, hr-03-executor-recovery, hr-04-decision-trace, hr-05-lifecycle-convergence, hr-06-flashcard-planning, hr-07-flashcard-jobs, hr-08-web-evidence-core, hr-09-web-admission, hr-10-sealed-contracts, hr-11-sealed-workflow
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Artifact-based CI closes releases 1.1-1.4 with deterministic offline evals and package scans; shared gate accepts 1.1/1.2/1.3 and HR-12 alone publishes final 1.4 with opt-in exact-Luna comparison.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-12 versioned report, offline thresholds, shared gate, artifact CI, Python 3.12/3.13 clean installs, optional live marker, and sole final publisher.
- README release waves, no Cardine/provider dependency, offline completeness, and final aggregate ownership.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-12-eval-release.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Fixed offline report and artifact gates fit one fresh Luna xhigh context without new runtime behavior.

## Context

HR-12 is the aggregate release bead and consumes all prior evidence while keeping live metrics separate from quality.

## What To Do

- Add versioned report/eval fixtures and shared RuntimeReleaseGate.
- Implement separate validity, coverage, unsupported-claim, reviewer-F1, replay, and package scans.
- Build/clean-install wheel and sdist on Python 3.12/3.13 without PYTHONPATH; keep live exact-Luna comparison opt-in.

## Likely Files / Packages

- tests/evals/runtime_release_report.py
- tests/evals/test_runtime_offline_release.py
- tests/evals/test_reviewer_macro_f1.py
- tests/evals/test_deterministic_replay.py
- tests/quality/test_future_runtime_distribution.py
- Harness-owned release configuration/scripts only where an existing package convention explicitly permits them

## Acceptance Criteria

- [ ] Offline schema/authority/citation/leak/coverage validity is 100%, unsupported claims zero, macro-F1 at least 0.95, replay deterministic.
- [ ] Shared gate accepts only passing 1.1/1.2/1.3; HR-12 alone emits 1.4/final aggregate.
- [ ] Clean Python 3.12/3.13 artifacts contain no Cardine/provider/secret/hidden entry-point leakage; separate test/eval, semantic, and package/security review gates pass.

## Verification

- `.venv/bin/python -m pytest tests/evals/test_runtime_offline_release.py tests/evals/test_reviewer_macro_f1.py tests/evals/test_deterministic_replay.py tests/quality/test_future_runtime_distribution.py`: expected to pass or produce documented output
- `.venv/bin/python -m pytest`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `.venv/bin/python -m build --wheel --sdist --outdir dist`: expected to pass or produce documented output
- `Clean-install both artifacts on Python 3.12 and 3.13 without PYTHONPATH`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- New runtime behavior, automatic model promotion, mandatory network/credentials, distributed JobStore, Cardine release, cost-based quality substitution, and paths outside eval/release configuration.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
