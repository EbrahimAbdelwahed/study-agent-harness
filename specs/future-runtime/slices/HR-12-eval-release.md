# HR-12 — Offline Evaluation and Runtime Release Gates

## Outcome

Close releases 1.1–1.4 with artifact-based CI, deterministic offline evals, package scans, and opt-in live comparison against the exact GPT-5.6 Luna baseline. Publish no wave that violates authority, replay, privacy, or sealed-content contracts.

## Non-goals

No automatic model promotion, mandatory credentials/network, cost-based quality substitution, Cardine release, distributed JobStore, or new runtime behavior.

## Contract and API seam

`tests/evals/runtime_release_report.py` emits a versioned report containing
schema/authority/citation/sealed-leak validity, required coverage,
unsupported claims, reviewer macro-F1, deterministic replay, and separate
cost/token/latency metrics. One shared `RuntimeReleaseGate` consumes the
release evidence from HR-05 (1.1), HR-07 (1.2), and HR-09 (1.3); HR-12 alone
consumes all prior reports and publishes the `1.4` final aggregate. CI builds
wheel/sdist, installs each artifact in clean Python 3.12/3.13 environments,
and verifies the curated API/import manifest. Live candidates run only behind
an explicit marker and compare to exact Luna; promotion requires no critical
failure and quality within three percentage points.

## Files and tests

- Add release report/eval fixtures under `tests/evals/` and package scripts only in Harness-owned release configuration.
- Add `tests/evals/test_runtime_offline_release.py`, `tests/evals/test_reviewer_macro_f1.py`, `tests/evals/test_deterministic_replay.py`, and `tests/quality/test_future_runtime_distribution.py`.

## Dependencies

HR-01–HR-11. The shared release gate receives HR-05/1.1, HR-07/1.2, and
HR-09/1.3 evidence; HR-12 requires HR-11 and is the only 1.4/final aggregate
publisher.

## Removal condition

No temporary fixture bypass, live-only acceptance path, or unpublished serializer remains after its wave is tagged. Optional adapters remain outside the base dependency set.

## Review surface

Review report schema, threshold vectors, artifact contents, import/entry-point manifest, no-Cardine scan, no-secret scan, and CI matrix on Python 3.12/3.13.

## Exact verification

```bash
.venv/bin/python -m pytest tests/evals/test_runtime_offline_release.py tests/evals/test_reviewer_macro_f1.py tests/evals/test_deterministic_replay.py tests/quality/test_future_runtime_distribution.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m build --wheel --sdist --outdir dist
```

Clean-install both artifacts without `PYTHONPATH`; run live comparison only
with an explicit opt-in marker and environment credential. Assert that no
earlier slice publishes `1.4` and that HR-12 is the sole final aggregate
publisher.

## Risks

Stale local archives, hidden source-checkout imports, or a live-only passing path can create a false release. CI requires fresh artifacts, clean installs, offline success, and archive scans before a tag.

## Definition of done

The shared gate accepts HR-05/1.1, HR-07/1.2, and HR-09/1.3 only after their
own evidence passes; HR-12 alone publishes the `1.4` final aggregate. Offline
validity is 100% for schemas, authority, citations, sealed leaks, and required
coverage; unsupported claims are zero; reviewer macro-F1 is at least 0.95;
replay is deterministic; live promotion rules are enforced; wheel/sdist
contain no Cardine references or mandatory provider dependency.
