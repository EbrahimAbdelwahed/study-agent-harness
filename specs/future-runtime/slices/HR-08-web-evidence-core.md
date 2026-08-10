# HR-08 — Quarantined Web Evidence Core

## Outcome

Add a provider-neutral WebEvidencePort and mandatory scripted offline connector that returns bounded, quarantined candidate evidence with provenance and partial-result semantics. The broker cannot admit evidence.

## Non-goals

No live network in the base package, arbitrary URL fetch, cookies, credentials, active-page execution, automatic admission, source replacement, or Cardine syllabus policy.

## Contract and API seam

`src/study_agent/ports/web_evidence.py:WebEvidencePort` returns `CandidateWebEvidence` with URL, hash, connector, query, timestamp, provenance, extracted-text bounds, and trust. `src/study_agent/web_evidence/broker.py:WebEvidenceBroker` enforces at most 8 queries/workflow, 10 candidates/query, 45s timeout, 256 KiB/candidate, HTTPS references, and 7-day candidate retention. Scripted fixtures are the default adapter and output is untrusted.

## Files and tests

- Add the port, broker/contracts, and scripted connector under `src/study_agent/web_evidence/`.
- Add `tests/unit/web_evidence/test_contracts.py`, `tests/contract/web_evidence/test_connector.py`, `tests/integration/test_scripted_web_evidence.py`, `tests/adversarial/test_web_candidate_quarantine.py`, and `tests/adversarial/test_web_limits.py`.

## Dependencies

HR-01 contracts, HR-03 bounded Jobs, HR-04 trace, and HR-05 lifecycle. HR-09 adds admission and optional live adapter.

## Removal condition

No connector writes SourceRevision or canonical events directly. Scripted offline behavior remains the complete verification path.

## Review surface

Review query/candidate limits, URL validation, connector trust labels, retention, partial network/error results, and prompt-injection-safe handling.

## Exact verification

```bash
.venv/bin/python -m pytest tests/unit/web_evidence/test_contracts.py tests/contract/web_evidence/test_connector.py tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py
```

Then run full offline suite without credentials or network.

## Risks

Untrusted connector text can contain instructions or secrets. The broker preserves candidate status, enforces bounds, and blocks authority shortcuts.

## Definition of done

Scripted connector is deterministic/offline; limits and quarantine are enforced; partial failures are explicit; no candidate is admitted or written as primary source.
