# Task Bead: hr-08-web-evidence-core Quarantined web evidence core

Status: Open
Priority: P1
Type: task
Depends On: hr-01-contract-firewall, hr-03-executor-recovery, hr-04-decision-trace, hr-05-lifecycle-convergence
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Provider-neutral WebEvidencePort and scripted offline connector return bounded quarantined candidates with provenance and explicit partial results; broker cannot admit or write SourceRevision.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-08 port, broker, scripted connector, limits, HTTPS validation, retention, and quarantine.
- README untrusted evidence, offline-first verification, and no arbitrary URL fetch.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/slices/HR-08-web-evidence-core.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Scripted offline connector and explicit security limits fit one fresh Luna xhigh context.

## Context

HR-08 is the web trust boundary; candidate text is untrusted and security review precedes HR-09.

## What To Do

- Add port, contracts, broker, and scripted connector.
- Enforce query/candidate/time/size/HTTPS/credential/retention bounds and partial results.
- Add quarantine, prompt-injection, credential, and limit fixtures without admission.

## Likely Files / Packages

- src/study_agent/ports/web_evidence.py
- src/study_agent/web_evidence/contracts.py
- src/study_agent/web_evidence/broker.py
- src/study_agent/web_evidence/scripted.py
- tests/unit/web_evidence/test_contracts.py
- tests/contract/web_evidence/test_connector.py
- tests/integration/test_scripted_web_evidence.py
- tests/adversarial/test_web_candidate_quarantine.py
- tests/adversarial/test_web_limits.py

## Acceptance Criteria

- [ ] Scripted connector is deterministic/offline/untrusted and candidate metadata round-trips exactly.
- [ ] Every HR-08 bound and partial failure is enforced; no candidate admits itself or writes canonical state.
- [ ] Focused test gate and separate independent semantic/security review gates pass.

## Verification

- `.venv/bin/python -m pytest tests/unit/web_evidence/test_contracts.py tests/contract/web_evidence/test_connector.py tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/ports/web_evidence.py src/study_agent/web_evidence tests/unit/web_evidence tests/contract/web_evidence tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- Admission, SourceRevision writes, arbitrary retrieval, live adapter, cookies/credentials, Cardine syllabus policy, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
