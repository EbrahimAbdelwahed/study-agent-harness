# ADR-0007: Gate optional dialogue with deterministic validator output

Date: 2026-07-15
Status: Accepted

## Context

The first tutor capabilities must act directly when the bounded task is ready,
ask one clarification only when it materially changes that task, and terminate
safely when evidence is unsupported. The v1 playbook is deliberately linear:
an unconditional `DialogueStep` always suspends, while a generic branch graph
would make checkpoint validation path-aware and turn the behavior layer toward
a workflow/planning engine.

## Decision

- Add an optional immutable `DialogueGate` to `DialogueStep`. It contains a
  `suspend_when` `DataReference` and a schema-valid default response.
- The condition must reference a nested boolean in the output of a previous
  `ValidateStep`. Model output cannot directly decide whether the core asks.
- When the condition is true, preserve the current suspend/CAS/resume behavior.
- When false, record a completed dialogue receipt with disposition `skipped`,
  persist the pinned default response, and continue linearly without suspension.
- Checkpoint inspection/recovery recomputes the gate from validated prior output
  and validates the trace shape and default response. Existing unconditional
  dialogue definitions and checkpoint receipts remain readable.
- Keep readiness validators narrow and capability-local. They may inspect
  explicit task fields and evidence, but cannot profile the learner, select a
  capability, or write canonical facts.

## Consequences

- One playbook supports direct and clarify-then-resume paths without a branch
  graph, second state owner, or host policy in the core.
- Both paths converge on the same final model and validation steps.
- The behavior layer gains one constrained conditional primitive whose decision
  remains deterministic and receipt-backed.
- Built-in capability tests must prove direct, skipped, suspended, resumed,
  malformed-condition, tamper, and legacy-dialogue behavior.

## Alternatives Considered

- Generic `BranchStep`: rejected because targets, path-aware traces, recovery,
  and branch attestation add disproportionate workflow-engine surface.
- Let the model decide and emit a suspension directive: rejected because it
  turns model output into unaudited local planning policy.
- Select one of two playbooks in the gateway: rejected because the gateway must
  execute the host-selected trusted binding, not choose behavior variants.
