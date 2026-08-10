# Task Bead: HR-12 Offline evaluation and runtime release gates

Status: Open
Priority: P1
Type: task
Depends On: HR-01-contract-firewall, HR-02-job-store, HR-03-executor-recovery, HR-04-decision-trace, HR-05-lifecycle-convergence, HR-06-flashcard-planning, HR-07-flashcard-jobs, HR-08-web-evidence-core, HR-09-web-admission, HR-10-sealed-contracts, HR-11-sealed-workflow

## Outcome

Artifact-based CI closes releases 1.1–1.4 with deterministic offline evals, package/import scans, and opt-in comparison against the exact GPT-5.6 Luna baseline. The shared RuntimeReleaseGate accepts 1.1/1.2/1.3 evidence, while HR-12 alone publishes the 1.4 final aggregate.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-12-eval-release.md`: versioned report, offline thresholds, shared gate, artifact CI, Python 3.12/3.13 clean installs, optional live marker, and sole final publisher.
- `specs/future-runtime/README.md`: release waves, no Cardine/provider dependency, offline completeness, and final aggregate ownership.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-12-eval-release.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a bounded offline eval/package gate with fixed report fields and no new runtime behavior. Execute in one fresh Luna xhigh context.

## Context

HR-12 is the aggregate release bead. It consumes evidence from every previous slice, keeps cost/token/latency separate from quality, and must prove no hidden source-checkout import, Cardine reference, mandatory provider, temporary bypass, or early 1.4 publisher remains.

## What To Do

- Add versioned release reports/eval fixtures under `tests/evals/` and Harness-owned release configuration only.
- Implement separate schema/authority/citation/leak/coverage/unsupported-claim/reviewer-F1/replay checks and the shared RuntimeReleaseGate.
- Build wheel/sdist and clean-install on Python 3.12 and 3.13 without `PYTHONPATH`; scan imports, entry points, Cardine strings, secrets, and optional dependencies.
- Keep live comparison explicitly marked, credentialed, and non-default; enforce no critical failure and quality within three percentage points of exact Luna for promotion.

## Likely Files / Packages

- `tests/evals/runtime_release_report.py`: versioned report and gate evidence.
- `tests/evals/test_runtime_offline_release.py`, `tests/evals/test_reviewer_macro_f1.py`, `tests/evals/test_deterministic_replay.py`: offline thresholds and replay.
- `tests/quality/test_future_runtime_distribution.py`: artifact/import/entry-point scans.
- Harness-owned release configuration/scripts only where existing package conventions permit.

## Acceptance Criteria

- [ ] Offline validity is 100% for schema, authority, citation, sealed-leak, and required coverage checks; unsupported claims are zero; reviewer macro-F1 is at least 0.95; replay is deterministic.
- [ ] Shared RuntimeReleaseGate accepts only passing HR-05/1.1, HR-07/1.2, and HR-09/1.3 evidence; HR-12 alone emits 1.4/final aggregate and earlier slices cannot publish it.
- [ ] Clean Python 3.12/3.13 wheel/sdist installs pass without `PYTHONPATH`; artifacts contain no Cardine reference, secret, mandatory provider, or hidden entry point.
- [ ] Test/eval gate and independent semantic/package security review are separate; opt-in live candidates compare to exact GPT-5.6 Luna with no critical failures and quality within three percentage points; cost/token/latency remain separate.

## Verification

- `.venv/bin/python -m pytest tests/evals/test_runtime_offline_release.py tests/evals/test_reviewer_macro_f1.py tests/evals/test_deterministic_replay.py tests/quality/test_future_runtime_distribution.py`: focused release gates pass.
- `.venv/bin/python -m pytest`: full offline suite passes.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m mypy`: repository gates pass.
- `.venv/bin/python -m build --wheel --sdist --outdir dist`: artifacts build.
- Clean-install both artifacts on Python 3.12 and 3.13 without `PYTHONPATH`; run import/entry-point/package scans.
- Live comparison runs only with an explicit marker and environment credential; default verification remains offline.
- `git diff --check`: clean.

## Out Of Scope

- New runtime behavior, automatic model promotion, mandatory credentials/network, distributed JobStore, Cardine release, cost-based quality substitution, and edits outside listed eval/release paths.

## Invariants

- Release waves are ordered 1.1 HR-05, 1.2 HR-07, 1.3 HR-09, and final 1.4 HR-12.
- Offline verification is a complete release path; live comparisons are opt-in evidence only.
- Optional adapters remain outside base dependency/import sets.

## Stop Conditions

- Stop if any earlier slice can publish 1.4, if artifact scans find Cardine/provider leakage, or if offline gates rely on credentials/network.
- Stop if reviewer, replay, leak, or coverage evidence is missing or below fixed thresholds.

## Review Gate

Test/eval results, independent semantic review, and package/security review are separate final prerequisites for publication.

## Notes / Handoff

- Root orchestrator runs the release runner after all 12 beads/briefs are materialized.
