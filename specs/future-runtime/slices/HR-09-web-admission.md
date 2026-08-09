# HR-09 — Web Evidence Admission and Optional Adapter

## Outcome

Allow only HUMAN or injected trusted SERVICE authority to admit an exact candidate snapshot. Record an immutable Source Revision receipt and provide an optional OpenAI Responses `web_search` adapter without changing the offline path.

## Non-goals

No broker auto-admission, model approval, arbitrary direct URL retrieval, credential/cookie forwarding, active execution, periodic syllabus search, or mandatory OpenAI dependency.

## Contract and API seam

`src/study_agent/web_evidence/admission.py:admit_snapshot` validates exact candidate hash, URL, query, connector, provenance, policy/version, authority, and timestamp, then calls the immutable source/revision owner. `src/study_agent/adapters/host/openai_responses.py:OpenAIResponsesWebSearch` implements WebEvidencePort behind the optional `openai` extra and is not imported by base modules.

## Files and tests

- Add admission service/receipt tests and the optional adapter under `src/study_agent/adapters/host/`.
- Add `tests/integration/test_web_evidence_admission.py`, `tests/adversarial/test_web_evidence_authority.py`, and `tests/unit/adapters/host/test_openai_responses_web_search.py`.

## Dependencies

HR-08 quarantine and existing source ingestion/revision ports. HR-12 owns optional live smoke and release metadata.

## Removal condition

No temporary connector bridge remains after all callers use WebEvidencePort; live adapter remains optional and outside base imports.

## Review surface

Review authority matrix, exact-byte receipt, source revision handoff, optional dependency boundary, safe query construction, and credential redaction.

## Exact verification

```bash
.venv/bin/python -m pytest tests/integration/test_web_evidence_admission.py tests/adversarial/test_web_evidence_authority.py tests/unit/adapters/host/test_openai_responses_web_search.py
.venv/bin/python -m pytest tests/architecture/test_oss_release_boundaries.py tests/quality/test_distribution_contents.py
```

Live smoke is permitted only with explicit credentials and an opt-in marker; default tests make no network call.

The shared release gate runs the positive scripted admission and authority
fixtures against a clean artifact and publishes release `1.3` through HR-09.

## Risks

Hash/metadata mismatch could admit altered content; authority confusion could make a provider approver. Tests reject both and preserve prior immutable revisions.

## Definition of done

Only trusted HUMAN/SERVICE admission creates SourceRevision; receipts are immutable/replayable; scripted tests remain complete; OpenAI adapter is optional, bounded, and credential-safe; and the shared release gate publishes `1.3` through HR-09.
