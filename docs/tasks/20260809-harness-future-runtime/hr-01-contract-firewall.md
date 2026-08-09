# Task Bead: hr-01-contract-firewall Runtime contract firewall

Status: Open
Priority: P1
Type: task
Depends On: none
Run ID: `20260809-harness-future-runtime`
Spec: `docs/specs/harness-future-runtime-features.md`

## Outcome

Harness exposes deterministic Job, attempt, lease, retry, suspension, resume-token, trace-reference, web-candidate, and sealed-verification contracts with adversarial rejection before runtime code.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- HR-01 contract/API seam, fixed defaults, identity, authority firewall, opaque references, and sealed-view deny-list.
- README one-lifecycle, untrusted MODEL, deterministic identity, bounded retries, and no learner-policy fields.
- Orchestrator records PF-11 stable-facade and CA-10 copied-core-removal/co-install evidence before dispatch.

## Grilling Evidence

- dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md § Approved Harness Future Runtime Contracts
- specs/future-runtime/README.md
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

Bounded contracts and adversarial fixtures fit one fresh Luna xhigh context without provider or persistence specialization.

## Context

HR-01 is the policy firewall and sole source of future-runtime vocabulary. PF-11 plus CA-10 is an orchestration gate, not a Harness import or schema dependency.

## What To Do

- Add the four production contract modules and four focused test/fixture areas named by HR-01.
- Encode the sole lifecycle, fixed defaults, fingerprints, retry classes, authority allowlist, opaque refs, and sealed-view checks.
- Reject MODEL authority, product policy, unbounded plans, mutable identity bytes, unknown retry classes, and sealed payloads.

## Likely Files / Packages

- src/study_agent/jobs/contracts.py
- src/study_agent/ports/jobs.py
- src/study_agent/runtime/policy_firewall.py
- src/study_agent/verification/contracts.py
- tests/unit/jobs/test_contracts.py
- tests/unit/verification/test_portable_refs.py
- tests/contract/jobs/test_golden_vectors.py
- tests/adversarial/test_runtime_policy_firewall.py
- tests/fixtures/jobs/**
- tests/fixtures/verification/**

## Acceptance Criteria

- [ ] All listed values round-trip deterministically with fixed defaults and golden vectors.
- [ ] Identity and child fingerprints reject changed bytes; authority, policy, retry, learner, and sealed fields fail closed.
- [ ] Focused contract/adversarial test gate and independent semantic/security review gate both pass; no Cardine, persistence, worker, or second lifecycle seam.

## Verification

- `.venv/bin/python -m pytest tests/unit/jobs/test_contracts.py tests/unit/verification/test_portable_refs.py tests/contract/jobs/test_golden_vectors.py tests/adversarial/test_runtime_policy_firewall.py`: expected to pass or produce documented output
- `.venv/bin/python -m ruff check src/study_agent/jobs src/study_agent/runtime src/study_agent/verification tests/unit/jobs tests/unit/verification tests/contract/jobs tests/adversarial/test_runtime_policy_firewall.py`: expected to pass or produce documented output
- `.venv/bin/python -m mypy`: expected to pass or produce documented output
- `git diff --check`: expected to pass or produce documented output

## Out Of Scope

- SQLite, executor, trace persistence, flashcard/web/sealed workflows, model/network calls, Cardine imports, curriculum/learner fields, and paths outside the allowlist.

## Notes / Handoff

- Worker must report files changed, behavior implemented, verification results, unresolved questions, and follow-up beads.
