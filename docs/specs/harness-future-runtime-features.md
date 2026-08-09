# Feature Spec: Harness Future Runtime Features

Status: Approved
Owner: orchestrator
Date: 2026-08-09
Run ID: `20260809-harness-future-runtime`

## Grilling Evidence

- Session/artifact: `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`
- Decision state: approved; all lifecycle, retry, privacy, web, sealed, novelty, and eval constants are closed.
- ADR/glossary changes: recorded in the handoff; no open decision remains.

## Goal

After PF-11 and Cardine CA-10, ship provider-neutral durable Jobs and Decision
Trace, hierarchical flashcard Jobs, quarantined web evidence, and sealed
Synthetic Verification in independent releases 1.1–1.4.

Canonical detail: `specs/future-runtime/README.md` and HR-01–HR-12.

## Problem

Current playbook, generation-worker, and lesson-worker flows have overlapping
outer lifecycle ownership and no generic durable Job/trace/web/sealed package
contracts. Future Cardine features need portable mechanisms without importing
Cardine policy or leaking operational/sealed state.

## Source Inputs

- Intake: `docs/flywheel-runs/20260809-harness-future-runtime/intake.md`
- Context pack: `docs/flywheel-runs/20260809-harness-future-runtime/context-pack.md`
- Canonical spec: `specs/future-runtime/README.md`

## Users

- Hosts executing recoverable bounded capabilities.
- Cardine consuming released opaque web/verification contracts.

## In Scope

- HR-01–HR-12: Job contracts/store/executor, minimal Decision Trace, lifecycle
  convergence, flashcard Job hierarchy, WebEvidence quarantine/admission,
  sealed grant/reveal/finalize workflow, and per-wave release/eval gates.

## Out of Scope

- Cardine curriculum, learner model, planning, attempts/grades/contests/UI/auth;
  distributed queues; arbitrary URL fetch; default telemetry; encryption claim;
  live network/model requirements in the offline path.

## User Stories

- As a host, I can recover at-least-once work while the owning domain commits
  an idempotent canonical outcome exactly once.
- As a learner-facing product, I can use quarantined evidence and progressive
  sealed presentation without exposing hidden content or surrendering authority.

## Domain Model

Owners: `Job`, attempt, lease/fencing, resume token, `JobStorePort`, executor,
`DecisionTraceEntry`, flashcard work plan, `CandidateWebEvidence`, admission
receipt, portable verification schemas, `PresentationGrant`, and answer grant.
Exact states, identities, limits, retention, and authority are in HR slices.

## API / Interface Contract

The public seams are `study_agent.api.jobs`, `.trace`, `.flashcards`,
`.web_evidence`, and `.verification`. HR-10/11 define opaque host-issued grants
and idempotent reveal/finalize operations; no raw host identity or sealed value
enters generic views.

## Prompt Behavior

- Prompt IDs affected: versioned worker/generator/reviewer prompts only.
- Course profile inputs: opaque pinned host refs.
- Output schema: typed candidates/proposals/coverage receipts.
- Grounding requirements: immutable source refs and claim-level citations.
- Eval fixtures required: scripted offline workers/connectors and exact release corpus.

## RAG / Source Grounding

- Required sources: generic SourceRevision/citation contracts from Foundation.
- Citation behavior: exact immutable pins; synthesis is never primary evidence.
- Unsupported-answer behavior: partial/failed result or blocked release, never silent support.

## UX Notes

- Loading state: host-owned; Job state is portable.
- Empty state: explicit no-candidate/no-coverage result.
- Error state: safe typed failures with correlation only.
- Accessibility: no Harness product UI; learner-safe DTOs support Cardine UI.

## Risks

- Lease races, duplicate delivery, trace privacy regression, prompt injection,
  lifecycle duplication, sealed serialization, and novelty false positives.

## Acceptance Criteria

- [ ] HR-01–HR-05 pass and release 1.1 with one generic lifecycle owner.
- [ ] HR-06/07 pass and release 1.2 with explicit partial flashcard proposals.
- [ ] HR-08/09 pass and release 1.3 with quarantine/admission authority.
- [ ] HR-10–HR-12 pass and release 1.4 with zero sealed leaks and approved evals.

## Verification

- Unit: state, identity, policy, redaction, novelty, and serialization vectors.
- Integration: crash/recovery, fencing, partial proposals, admission, sealed workflow.
- Evals: required coverage 100%, unsupported claims zero, reviewer macro-F1 ≥0.95, replay equality.
- Manual: inspect release reports and learner-safe serialized surfaces.

## Open Questions

- None. All public states, numeric defaults, authority, retention, and releases are fixed.

## Task Beads

- `HR-01`: Contract firewall and Job identity
- `HR-02`: Durable JobStore and fencing
- `HR-03`: Executor, retry, cancellation, and resume
- `HR-04`: Decision Trace and diagnostics
- `HR-05`: Generic lifecycle convergence and release 1.1
- `HR-06`: Flashcard planning contracts
- `HR-07`: Flashcard Job composition and release 1.2
- `HR-08`: Quarantined web-evidence core
- `HR-09`: Admission, optional adapter, and release 1.3
- `HR-10`: Sealed contracts, grant protocol, and leak oracle
- `HR-11`: Generation, independent review, release, and presentation
- `HR-12`: Final eval and release 1.4
