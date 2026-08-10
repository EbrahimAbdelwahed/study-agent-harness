# Task Bead: hr-09-web-admission Web evidence admission and optional adapter

Status: Open
Priority: P1
Type: task
Depends On: hr-08-web-evidence-core
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Only HUMAN or injected trusted SERVICE admits an exact candidate snapshot into immutable SourceRevision; optional OpenAI Responses web_search remains outside base imports and release 1.3 is gated.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-09 exact snapshot admission, receipt fields, authority matrix, optional adapter boundary, and release 1.3.
- README trusted admission, immutable source identity, no provider authority, and optional dependencies.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-09-web-admission.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Authority/receipt boundary and optional adapter fit one fresh Luna xhigh context with security review.

## Context

HR-09 consumes quarantined candidates and source revision ports; admission validates exact bytes and metadata before immutable handoff.

## What To Do

- Add admit_snapshot and immutable receipt tests.
- Add optional OpenAI Responses adapter behind openai extra with fake transport and credential redaction.
- Keep scripted path complete and add release 1.3 evidence after separate test/import, semantic, and security gates.

## Likely Files / Packages

- src/study_agent/web_evidence/admission.py
- src/study_agent/adapters/host/openai_responses.py
- tests/integration/test_web_evidence_admission.py
- tests/adversarial/test_web_evidence_authority.py
- tests/unit/adapters/host/test_openai_responses_web_search.py
- tests/architecture/test_oss_release_boundaries.py
- tests/quality/test_distribution_contents.py

## Acceptance Criteria

- [ ] Exact bytes and metadata match before HUMAN/SERVICE creates one immutable SourceRevision; MODEL/broker/mismatch fails closed.
- [ ] Optional adapter is bounded/credential-safe/absent from base imports; default path is offline.
- [ ] Separate test/import, semantic, and security review gates pass; shared gate publishes 1.3 only.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_web_evidence_admission.py tests/adversarial/test_web_evidence_authority.py tests/unit/adapters/host/test_openai_responses_web_search.py`: expected to pass or produce documented output
- `.venv/bin/python -m pytest tests/architecture/test_oss_release_boundaries.py tests/quality/test_distribution_contents.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check .`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Auto-admission, MODEL approval, arbitrary retrieval, mandatory OpenAI, Cardine policy, and release behavior outside the shared gate.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
