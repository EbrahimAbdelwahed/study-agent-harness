# ADR-0004: Keep adaptive tutor choice in the host

Date: 2026-07-14
Status: Accepted

## Context

The harness must support a tutor that starts from any learner request and
chooses what to explain, ask, generate, or review from incomplete evolving
context. Encoding that freedom as one large playbook would turn an adaptive
tutor into a rigid workflow. Moving study policy into an agent SDK or model
adapter would instead fork behavior by runtime and provider.

The existing architecture already makes the per-course event stream canonical,
skills and playbooks versioned behavior, and model adapters technical
transports. It also separates trusted host authority from model-proposed tool
arguments.

## Decision

- An external Tutor Host owns the bounded agent loop and selects the next
  advertised study capability.
- The core exposes sequence-consistent tutor snapshots and a trusted capability
  gateway over built-in skills and playbooks.
- Each capability is a finite or suspendable procedure with schema, policy,
  validators, provenance, idempotency, and explicit state-write permissions.
- The host supplies principal, repository, course, session, capability grants,
  correlation, and retry identity out of band. Model output cannot select them.
- Learner declarations and observed outcomes are canonical events. Estimates,
  hypotheses, and candidate actions remain derived or operational and name the
  evidence that produced them.
- API-key and subscription integrations are separate host adapters over the
  same core contracts; neither changes domain behavior.

## Consequences

- An agent may meet the learner at any point without a mandatory onboarding
  funnel.
- Agent runtimes can vary without duplicating prompts, pedagogy, or canonical
  state rules.
- The core gains context, artifact, assessment, evidence, and recall owners but
  not a generic autonomous planner.
- Capability manifests and tutor snapshots become public compatibility
  surfaces and require contract tests.
- Hosts must bound step count, interruption, authority, and retries.

## Alternatives Considered

- One end-to-end tutor playbook: rejected because global order would be rigid
  and checkpoints would become a substitute for agent judgment.
- Put tutoring in the OpenAI/agent adapter: rejected because behavior would fork
  across models and runtimes.
- Store a model-authored learner biography as truth: rejected because it is not
  replayable evidence and silently promotes inference to authority.
- Let the model invoke arbitrary persistence commands: rejected because model
  output cannot acquire repository or canonical-write authority.
