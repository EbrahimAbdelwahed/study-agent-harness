# Harness Future Runtime Features

Status: ready for implementation planning

Date: 2026-08-09

Owning repository: Study Agent Harness

## Outcome

Add the provider-neutral runtime waves approved in the Cardine/Harness handoff:
one durable Job lifecycle, a separate minimal Decision Trace, hierarchical
flashcard Jobs, quarantined web evidence, and sealed Synthetic Verification.
The package remains local-first, offline-verifiable, and independent of
Cardine. Cardine receives only released portable contracts and presentation
receipts; it owns academic authority, attempts, grades, contests, curriculum,
learner estimates, and planning.

## Scope firewall

Harness owns Job/lease/attempt/retry mechanics, executor checkpoints,
provider-neutral evidence transport and quarantine, portable exam-generation
schemas, validation, replay, and trust boundaries. Harness does not own
curriculum meaning, mastery, readiness, study planning, exam authenticity,
grades, contests, UI, auth, or deployment. All host academic references are
opaque typed IDs. A model is an untrusted provider and can never approve,
admit evidence, release content, or commit a canonical product fact.

The sole outer lifecycle is:

```text
QUEUED -> RUNNING -> SUSPENDED | SUCCEEDED | FAILED | CANCELLED | STALE
```

Lease and heartbeat are RUNNING metadata. Retries create monotonic attempts
under the same Job. Existing playbook and lesson-worker checkpoints are
subordinate proofs, not a second lifecycle owner.

## Slice graph

```text
HR-01 -> HR-02 -> HR-03 -> HR-04 -> HR-05
                       |
                       +-> HR-06 -> HR-07
                       +-> HR-08 -> HR-09
                       +-> HR-10 -> HR-11
HR-05 -> shared RuntimeReleaseGate -> publishes 1.1
HR-07 -> shared RuntimeReleaseGate -> publishes 1.2
HR-09 -> shared RuntimeReleaseGate -> publishes 1.3
HR-11 -> HR-12 -> shared RuntimeReleaseGate -> publishes 1.4/final aggregate
```

Risk-first order is intentional: HR-01 installs the policy firewall and
adversarial leak oracles before runtime implementations; HR-05 proves lifecycle
convergence before old stores are removed; HR-10 proves sealed-content
non-disclosure before generation exists.

## Release waves

| Release | Slice and gate producer | Shipped contract |
| --- | --- | --- |
| 1.1 | HR-01–HR-05, published by HR-05 through `RuntimeReleaseGate` | JobStore, executor recovery, and minimal Decision Trace |
| 1.2 | HR-06–HR-07, published by HR-07 through the same `RuntimeReleaseGate` | Hierarchical flashcard Jobs and proposal-only assembly |
| 1.3 | HR-08–HR-09, published by HR-09 through the same `RuntimeReleaseGate` | Quarantined WebEvidencePort and explicit admission |
| 1.4 | HR-10–HR-12, final aggregate published only by HR-12 through `RuntimeReleaseGate` | Sealed Synthetic Verification, offline evals, and package release |

The base package remains dependency-free. The scripted web connector is in
the base runtime. OpenAI Responses `web_search` and OpenTelemetry are optional
adapters. No live network call is part of the default verification path.

## Program orchestration gate

Runtime implementation may start only after PF-11 has promoted the stable
facade and CA-10 has supplied its copied-core-removal/co-install evidence.
This is a program-level ordering gate recorded by the orchestrator; it is not
a Harness source, import, package, schema, or test dependency. HR slices must
continue to name only released Harness contracts and generic ports.

## Shared contracts and invariants

- Every durable command carries an idempotency key. Same key and canonical
  input converge; same key and different bytes return conflict.
- Job identity is derived from capability/version, authority scope,
  idempotency key, and input fingerprints. Child identity also includes parent,
  position, and task fingerprint. Same identity with different bytes conflicts.
- Defaults are fixed: 60-second lease, 20-second heartbeat, fencing on expiry,
  global and per-workflow concurrency 8, depth 1, maximum 64 children, FIFO
  deterministic claims, at-least-once execution, and owner-idempotent exactly
  once canonical commit.
- Retry defaults are maximum three attempts, 1/2/4 second exponential
  backoff, +/-20% jitter, and 30-second cap. Only timeout, rate limit,
  provider-5xx, or declared transient failures retry.
- Cancellation completes at a safe point. A committed event is never rolled
  back. Suspended Jobs hold no lease; resume tokens bind Job, attempt,
  checkpoint, authority, input, and dependency fingerprints.
- Decision Trace is separate append-only audit evidence. It records observable
  IDs, transitions, validators, safe errors, fingerprints, and timestamps; it
  never stores prompts, excerpts, outputs, secrets, raw personal identity, or
  chain-of-thought. Redacted diagnostics expire after 14 days; optional
  telemetry loss cannot change execution.
- Web candidates are quarantined and untrusted. The broker cannot admit.
  Admission of an exact snapshot by HUMAN or trusted SERVICE creates an
  immutable Source Revision with hash, URL, time, connector, query,
  provenance, policy, and decision.
- Sealed means application authority, not encryption. Lists, search, export,
  traces, errors, and pre-attempt presentation contain no sealed questions or
  answers.
- Synthetic Verification requires approved profile and accepted plan,
  independent coverage review, deterministic release, complete required
  coverage, and no unsupported claims. Generator output never self-reviews or
  self-releases.
- No Job, trace, diagnostic, cache, checkpoint, or operational run record is
  learner truth or enters a product projection/export.

## Review map

Current implementation seams to preserve are `src/study_agent/lifecycle/`,
`src/study_agent/workers/`, `src/study_agent/flashcards/`,
`src/study_agent/capabilities/`, `src/study_agent/artifacts/`,
`src/study_agent/adapters/sqlite/`, and `src/study_agent/ports/`. New seams are
the JobStore/Executor ports, TraceStore, WebEvidencePort, sealed verification
contracts, and their SQLite/scripted adapters. Each slice names its exact
review files and tests.

## Global verification

Run the narrow slice command first, then from the Harness root:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
git diff --check
```

For each release wave, build and test the artifact in a clean Python 3.12 and
3.13 environment. The wheel must contain no Cardine references, no required
provider dependency, and no hidden entry point. Offline tests must run without
credentials or network. Live connector and model comparisons are opt-in.

## Transition removals

HR-05 removes only the generic lifecycle, playbook, and GenerationWorker outer
transitions after parity proves Job recovery, suspension, continuation, and
gateway outcomes. HR-07 removes only the flashcard LessonWorker transitions
after hierarchical flashcard parity. No temporary adapter survives the named
last consumer. Diagnostic payloads never become Trace; Trace never becomes a
domain event. Candidate web content never becomes a Source Revision without
admission. Sealed content never enters generic views.

## Residual risks

Lease races, duplicate delivery, and exactly-once canonical commit remain
possible failure modes and require the adversarial fixtures in HR-02/03.
Trace redaction can regress as fields evolve; HR-04 owns schema deny-lists and
scanners. Web connectors can return prompt-injection or false evidence; HR-08/09
keep output untrusted and quarantined. Novelty thresholds can over-regenerate;
HR-10/11 suspend after two failed regenerations and expose no content. SQLite
is local single-writer; distributed queue behavior is not part of these waves.

## Next Agent Prompt

You are implementing the Harness Future Runtime Features spec. Start with
`slices/HR-01-contract-firewall.md`; add only the contract and adversarial
fixtures named there, then run its exact verification command and the global
offline checks. Do not add Cardine policy, a second lifecycle owner, live
network defaults, or sealed-content serialization. Continue slices in graph
order, recording any changed evidence in this README before ending your pass.
Update the status, next pickup point, and checklist here before handing off.

Global checklist:

- [ ] HR-01–HR-05 and shared release gate publishes 1.1
- [ ] HR-06–HR-07 and shared release gate publishes 1.2
- [ ] HR-08–HR-09 and shared release gate publishes 1.3
- [ ] HR-10–HR-12 and HR-12-only final aggregate publishes 1.4
- [ ] Program gate records PF-11 and CA-10 evidence before runtime start
- [ ] Remove every temporary lifecycle seam at its named removal slice
- [ ] Re-run full offline suite on Python 3.12 and 3.13
