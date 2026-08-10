# Task Bead: HR-09 Web evidence admission and optional adapter

Status: Open
Priority: P1
Type: task
Depends On: HR-08-web-evidence-core

## Outcome

Only HUMAN or injected trusted SERVICE authority admits an exact candidate snapshot into an immutable Source Revision receipt. The scripted path remains complete offline behavior; an optional OpenAI Responses `web_search` adapter stays outside base imports. Release 1.3 is published through the shared RuntimeReleaseGate.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-09-web-admission.md`: exact snapshot admission, receipt fields, authority matrix, optional adapter boundary, and release 1.3.
- `specs/future-runtime/README.md`: trusted admission, immutable source identity, no provider authority, and optional dependencies.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-09-web-admission.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

The bead is a bounded authority/receipt boundary plus an optional adapter. Execute in one fresh Luna xhigh context with a separate security review.

## Context

HR-09 consumes HR-08 quarantined candidates and existing source revision ports. Admission validates exact bytes and metadata before immutable source handoff; no broker or MODEL approval is permitted.

## What To Do

- Add `admit_snapshot` and immutable receipt tests for hash, URL, query, connector, provenance, policy/version, authority, and timestamp.
- Add optional `OpenAIResponsesWebSearch` behind the `openai` extra without importing it from base modules; bound queries and redact credentials.
- Preserve scripted positive/negative admission and source revision replay; keep live smoke opt-in.
- Add shared RuntimeReleaseGate evidence for release 1.3.

## Likely Files / Packages

- `src/study_agent/web_evidence/admission.py`: exact snapshot authority and source handoff.
- `src/study_agent/adapters/host/openai_responses.py`: optional WebEvidencePort adapter only.
- `tests/integration/test_web_evidence_admission.py`: positive receipt/source replay.
- `tests/adversarial/test_web_evidence_authority.py`: HUMAN/SERVICE/MODEL and mismatch failures.
- `tests/unit/adapters/host/test_openai_responses_web_search.py`: inert optional adapter with fake transport.
- `tests/architecture/test_oss_release_boundaries.py`, `tests/quality/test_distribution_contents.py`: import/dependency boundary.

## Acceptance Criteria

- [ ] Exact candidate bytes and all receipt metadata must match before HUMAN or injected SERVICE admission creates one immutable SourceRevision; MODEL/broker/changed bytes fail closed.
- [ ] Scripted offline admission is deterministic and complete; optional adapter is bounded, credential-safe, and absent from base imports/dependencies.
- [ ] No arbitrary URL fetch, cookies, active execution, periodic search, source replacement, or canonical duplicate write is introduced.
- [ ] Focused authority/import tests pass; independent semantic and security reviews separately approve receipt integrity, credential redaction, and optional boundary; the shared RuntimeReleaseGate publishes only 1.3.

## Verification

- `.venv/bin/python -m pytest tests/integration/test_web_evidence_admission.py tests/adversarial/test_web_evidence_authority.py tests/unit/adapters/host/test_openai_responses_web_search.py`: focused tests pass.
- `.venv/bin/python -m pytest tests/architecture/test_oss_release_boundaries.py tests/quality/test_distribution_contents.py`: package boundaries pass.
- `.venv/bin/python -m pytest`: default suite makes no network call.
- `.venv/bin/python -m ruff check .` and `.venv/bin/python -m mypy`: repository gates pass.
- `git diff --check`: clean.
- Opt-in live smoke may run only with explicit credentials and marker; release gate remains offline.

## Out Of Scope

- Broker auto-admission, MODEL approval, arbitrary retrieval, mandatory OpenAI dependency, Cardine syllabus policy, and edits outside listed paths.

## Invariants

- Admission is the only path from candidate to immutable SourceRevision.
- Optional live adapter never changes scripted/offline behavior or base imports.
- Release 1.3 is emitted only by the shared gate after HR-09 evidence passes.

## Stop Conditions

- Stop if metadata/hash validation can be bypassed or credentials can enter requests, receipts, traces, errors, or reprs.
- Stop if optional adapter requires network or credentials in default tests.

## Review Gate

Test/import, independent semantic, and independent security gates are separate prerequisites for release 1.3.

## Notes / Handoff

- HR-12 consumes the 1.3 evidence; HR-10/11 do not depend on web slices.
