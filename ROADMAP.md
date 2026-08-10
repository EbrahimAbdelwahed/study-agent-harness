# Study Agent Harness Roadmap

This is the public home for approved future work. It is intentionally ordered,
not dated, and contains no specs or beads. Each phase must preserve the
invariants in [`CONTEXT.md`](CONTEXT.md) and the ownership map in
[`CONTEXT-MAP.md`](CONTEXT-MAP.md). Detailed implementation work belongs in
future specs and beads.

## Phases

1. **Integrated baseline** — preserve the existing offline harness, immutable
   KB, replay/export guarantees, recall, feedback, and reference CLI while
   consolidating the host boundary and contributor workflow.
2. **Real assembly and developer API** — compose model adapter → host runner →
   capability gateway through a small typed developer surface. Keep async as
   the one runtime and provide sync convenience only as a facade.
3. **Job kernel and observability** — add generic durable job/workflow
   lifecycle, leases, retries, suspension, and canonical Decision Trace. Use
   SQLite locally with a port for future distributed backends; retain
   diagnostic-local redacted logs for 14 days by default.
4. **Hierarchical generation** — install a bounded flashcard worker with
   deterministic coordinator/leaf jobs, separate review, deterministic
   assembly, partial-gap semantics, and proposal-only persistence.
5. **Web evidence** — install a quarantined WebEvidenceBroker that returns
   candidate evidence with claim lineage and trust metadata. Admission, not the
   connector, decides whether evidence becomes eligible for grounded use;
   derived synthesis retains claim-level lineage and never becomes a primary
   source.
6. **Sealed assessments** — implement approved versioned Exam Profiles,
   Generation Plans, sealed Synthetic Verification, attempts, separate
   structured coverage review, deterministic policy gates, and stale-input
   audit/targeted regeneration.
7. **Eval, package, and Cardine consumption** — publish offline fixture evals
   plus opt-in live model comparisons against Luna; version the installable
   package and let Cardine consume it without source copies.

## Acceptance principles

- Every phase has a provider-neutral contract, focused fixtures, replayable
  outcomes, and a documented owner before implementation begins.
- Canonical state is append-only and replayable; operational indexes,
  checkpoints, traces, and job leases remain discardable or reconstructible.
- Model output is untrusted input. Validation, permissions, provenance, and
  human/policy decisions remain harness-owned.
- Offline operation remains a complete quality path. Network, live models,
  browser connectors, and telemetry are explicit opt-ins.
- New workers are capabilities behind generic lifecycle ports, not kernel
  special cases or autonomous subagent swarms.
- Evaluation reports compare candidate behavior with the Luna baseline using
  effective quality, grounding, coverage, conformance, latency, token, and
  cost metrics; a model is not silently promoted by availability alone.

## Non-goals

- No Pi/runtime dependency, vendoring, or provider-specific study behavior.
- No hosted product, authentication, organizations, billing, multi-tenant
  service, or remote telemetry default.
- No arbitrary model-authored persistence, hidden chain-of-thought capture, or
  automatic artifact acceptance.
- No general-purpose subagent framework, unbounded parallel generation, or
  worker-owned canonical policy.
- No cross-user sharing or collaborative approval model in this sequence.

The current implementation and accepted behavior decisions remain authoritative;
this roadmap records only the approved direction. See the [decision index](docs/decisions/)
and [`CONTEXT-MAP.md`](CONTEXT-MAP.md) before proposing a new phase.
