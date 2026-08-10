# Worker Brief: HR-09

## Assignment

Implement `HR-09-web-admission` from `specs/future-runtime/slices/HR-09-web-admission.md`.

Worker target: Luna xhigh. Execute only this admission/optional-adapter bead after HR-08.

## Read First

- `AGENTS.md`
- `CONTEXT.md` and `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- `specs/future-runtime/README.md`
- `specs/future-runtime/slices/HR-09-web-admission.md`
- `specs/future-runtime/beads/HR-09-web-admission.md`
- HR-08 web contracts and existing source ingestion/revision ports

## Scope

You may change:

- `src/study_agent/web_evidence/admission.py`
- `src/study_agent/adapters/host/openai_responses.py`
- `tests/integration/test_web_evidence_admission.py`
- `tests/adversarial/test_web_evidence_authority.py`
- `tests/unit/adapters/host/test_openai_responses_web_search.py`
- `tests/architecture/test_oss_release_boundaries.py`
- `tests/quality/test_distribution_contents.py`

Do not change:

- Paths outside the allowlist, including broker behavior, Cardine syllabus policy, mandatory OpenAI dependencies, arbitrary URL retrieval, credentials in default tests, and release behavior outside the shared gate.

## Requirements

- Validate exact bytes/hash and URL/query/connector/provenance/policy/version/authority/timestamp before one immutable SourceRevision handoff.
- Permit HUMAN or injected trusted SERVICE only; MODEL, broker, changed metadata, and changed bytes fail closed.
- Keep OpenAI Responses `web_search` optional, bounded, credential-safe, and absent from base imports; scripted offline path remains complete.
- Add release 1.3 evidence only after separate test/import, semantic, and security review gates.

## Acceptance Criteria

- Admission receipts are immutable/replayable and source revisions are not duplicated or replaced.
- Optional adapter tests use fake transport; default tests make no network call or credential access.
- Shared RuntimeReleaseGate publishes 1.3 only after all gates pass.

## Verification

Run:

```bash
.venv/bin/python -m pytest tests/integration/test_web_evidence_admission.py tests/adversarial/test_web_evidence_authority.py tests/unit/adapters/host/test_openai_responses_web_search.py
.venv/bin/python -m pytest tests/architecture/test_oss_release_boundaries.py tests/quality/test_distribution_contents.py
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

## Report Back

Return files changed, admission/adapter behavior, exact commands/results, scope constraints followed, unresolved questions, and follow-up beads.
