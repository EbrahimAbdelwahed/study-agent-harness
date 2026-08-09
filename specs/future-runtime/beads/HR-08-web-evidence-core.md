# Task Bead: HR-08 Quarantined web evidence core

Status: Open
Priority: P1
Type: task
Depends On: HR-01-contract-firewall, HR-03-executor-recovery, HR-04-decision-trace, HR-05-lifecycle-convergence

## Outcome

Provider-neutral WebEvidencePort and a mandatory scripted offline connector return bounded, quarantined CandidateWebEvidence with provenance and explicit partial-result semantics. The broker cannot admit evidence or write a SourceRevision.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-08-web-evidence-core.md`: port, broker, scripted connector, limits, HTTPS validation, retention, and quarantine.
- `specs/future-runtime/README.md`: untrusted evidence, offline-first verification, and no arbitrary URL fetch.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/slices/HR-08-web-evidence-core.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a provider-neutral, scripted, offline connector with explicit security limits. Execute in one fresh Luna xhigh context; no live adapter is in scope.

## Context

HR-08 introduces the web trust boundary. Candidate text is untrusted input and may contain prompt injection or secrets. Security review is required before HR-09 admission work.

## What To Do

- Add WebEvidencePort, CandidateWebEvidence/broker contracts, and scripted connector under `src/study_agent/web_evidence/`.
- Enforce at most 8 queries/workflow, 10 candidates/query, 45s timeout, 256 KiB/candidate, HTTPS-only references, no cookies/credentials/active execution, and 7-day candidate retention.
- Preserve connector/query/provenance/hash/timestamp/trust metadata and return explicit partial results on scripted/network failures.
- Add quarantine, prompt-injection-safe, bound, and retention fixtures; do not add admission.

## Likely Files / Packages

- `src/study_agent/ports/web_evidence.py`: provider-neutral port.
- `src/study_agent/web_evidence/contracts.py`, `src/study_agent/web_evidence/broker.py`: bounded candidate and broker behavior.
- `src/study_agent/web_evidence/scripted.py`: deterministic offline connector.
- `tests/unit/web_evidence/test_contracts.py`, `tests/contract/web_evidence/test_connector.py`: contracts.
- `tests/integration/test_scripted_web_evidence.py`: offline flows.
- `tests/adversarial/test_web_candidate_quarantine.py`, `tests/adversarial/test_web_limits.py`: security and limit fixtures.

## Acceptance Criteria

- [ ] Scripted connector is deterministic, offline, and untrusted; candidate bytes, hashes, provenance, URL, connector, query, time, and trust round-trip exactly.
- [ ] Broker enforces every query/candidate/timeout/size/HTTPS/retention limit and reports partial failures explicitly.
- [ ] No candidate can admit itself, write SourceRevision, append canonical events, forward credentials, execute active content, or bypass HUMAN/SERVICE authority.
- [ ] Focused quarantine/limit test gate passes; independent semantic and security review gates confirm prompt-injection, credential, and authority isolation.

## Verification

- `.venv/bin/python -m pytest tests/unit/web_evidence/test_contracts.py tests/contract/web_evidence/test_connector.py tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py`: focused tests pass.
- `.venv/bin/python -m pytest`: global offline suite runs without credentials or network.
- `.venv/bin/python -m ruff check src/study_agent/ports/web_evidence.py src/study_agent/web_evidence tests/unit/web_evidence tests/contract/web_evidence tests/integration/test_scripted_web_evidence.py tests/adversarial/test_web_candidate_quarantine.py tests/adversarial/test_web_limits.py`: lint passes.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- Admission, SourceRevision writes, arbitrary URL retrieval, live OpenAI adapter, cookies/credentials, Cardine syllabus policy, and edits outside listed paths.

## Invariants

- Candidate web evidence is quarantined and untrusted until HR-09 admission.
- Scripted offline behavior is the complete default verification path.
- The broker has no admission authority.

## Stop Conditions

- Stop if a connector needs live network, credentials, active-page execution, or a new dependency in base core.
- Stop if any candidate path can write canonical source or product state.

## Review Gate

Focused tests and separate independent semantic/security reviews are required before HR-09.

## Notes / Handoff

- HR-09 adds trusted admission and the optional OpenAI Responses adapter.
