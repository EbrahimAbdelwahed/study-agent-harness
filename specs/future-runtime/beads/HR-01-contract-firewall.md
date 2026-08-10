# Task Bead: HR-01 Runtime contract firewall

Status: Open
Priority: P1
Type: task
Depends On: none

## Outcome

Harness exposes deterministic Job, attempt, lease, retry, suspension, resume-token, trace-reference, web-candidate, and sealed-verification contracts. Adversarial fixtures reject invalid lifecycle, authority, policy, identity, and sealed-view inputs before runtime code is added.

## Slice Strategy

tracer-bullet

Fresh Context Fit: yes

## Spec Coverage

- `specs/future-runtime/slices/HR-01-contract-firewall.md`: all contract/API, fixed-default, identity, authority-firewall, opaque-reference, and sealed-view criteria.
- `specs/future-runtime/README.md`: one lifecycle, untrusted MODEL, deterministic identity, bounded retries, and no learner-policy fields.
- Program ordering gate: PF-11 stable-facade promotion and CA-10 copied-core-removal/co-install evidence are recorded by the orchestrator before dispatch.

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md` § Approved Harness Future Runtime Contracts; `specs/future-runtime/README.md`.
- Decision state: approved
- ADR/glossary changes: none

## Worker Profile

none needed

Rationale:

This is a bounded contract and adversarial-fixture pass with fixed fields and no provider or persistence specialization. Execute in one fresh Luna xhigh context.

## Context

HR-01 is the policy firewall and the sole source of future-runtime vocabulary. The implementation must remain Harness-only and must not infer Cardine curriculum, mastery, readiness, planning, or learner identity. The PF-11 + CA-10 program precondition is an orchestration gate, not an import or schema dependency.

## What To Do

- Add the four production contract modules and the four focused test/fixture areas named by HR-01.
- Encode the sole Job lifecycle, identity fingerprints, fixed numeric defaults, retry classes, authority allowlist, and opaque verification references.
- Reject MODEL authority, product-policy fields, unbounded child plans, mutable identity bytes, unknown retry classes, and sealed payloads in generic views.
- Keep fixtures opaque and deterministic; preserve the owner-only canonical commit boundary for later slices.

## Likely Files / Packages

- `src/study_agent/jobs/contracts.py`: Job, attempt, lease, retry, checkpoint, resume-token, and identity values.
- `src/study_agent/ports/jobs.py`: JobStorePort and JobExecutorPort contracts.
- `src/study_agent/runtime/policy_firewall.py`: authority, policy, retry, child-bound, and safe-view validation.
- `src/study_agent/verification/contracts.py`: opaque exam/profile/plan/verification references and PresentationReceipt.
- `tests/unit/jobs/test_contracts.py`, `tests/unit/verification/test_portable_refs.py`, `tests/contract/jobs/test_golden_vectors.py`, `tests/adversarial/test_runtime_policy_firewall.py`: focused coverage.
- `tests/fixtures/jobs/**`, `tests/fixtures/verification/**`: opaque-ID golden fixtures only.

## Acceptance Criteria

- [ ] All listed values validate and round-trip through deterministic canonical bytes with the fixed defaults: 60s lease, 20s heartbeat, concurrency 8, depth 1, 64 children, three attempts, 1/2/4s backoff, ±20% jitter, and 30s cap.
- [ ] Job identity includes capability/version, authority scope, idempotency key, and input fingerprints; child identity also includes parent, position, and task fingerprint; equal identity with changed bytes fails closed.
- [ ] Only HUMAN or trusted SERVICE authority is accepted for durable effects; MODEL, product-policy fields, unbounded plans, unsupported retries, and learner fields are rejected before side effects.
- [ ] Generic views cannot serialize sealed questions/answers or raw identity, and all references remain opaque typed IDs.
- [ ] Focused contract and adversarial test gate passes; an independent semantic review gate confirms no Cardine import, persistence, worker, or second lifecycle seam.

## Verification

- `.venv/bin/python -m pytest tests/unit/jobs/test_contracts.py tests/unit/verification/test_portable_refs.py tests/contract/jobs/test_golden_vectors.py tests/adversarial/test_runtime_policy_firewall.py`: all focused tests pass.
- `.venv/bin/python -m ruff check src/study_agent/jobs src/study_agent/runtime src/study_agent/verification tests/unit/jobs tests/unit/verification tests/contract/jobs tests/adversarial/test_runtime_policy_firewall.py`: lint passes.
- `.venv/bin/python -m pytest`: global offline suite remains green.
- `.venv/bin/python -m mypy`: strict typing remains green.
- `git diff --check`: clean.

## Out Of Scope

- SQLite JobStore, executor loop, Decision Trace persistence, flashcard/web/sealed workflow behavior, model calls, network, Cardine imports, curriculum fields, and learner-facing content.
- Changes outside the listed production/test/fixture paths.
- Any new dependency, public facade expansion, or alternate lifecycle owner.

## Invariants

- The sole outer lifecycle is `QUEUED -> RUNNING -> SUSPENDED | SUCCEEDED | FAILED | CANCELLED | STALE`.
- Leases and heartbeats are RUNNING metadata; retries are monotonic attempts under one Job.
- Model output never approves, admits, releases, or commits canonical state.

## Stop Conditions

- Stop before editing if PF-11 and CA-10 evidence is not recorded by the orchestrator.
- Stop and report if a required field would add Cardine policy, learner truth, a second lifecycle, or a dependency.

## Review Gate

Focused tests and an independent semantic/security review must both pass before HR-02 is dispatched.

## Notes / Handoff

- HR-01 blocks HR-02 through HR-12 implementation dispatch.
- Worker reports files changed, behavior, exact command results, constraints followed, unresolved questions, and follow-up beads.
