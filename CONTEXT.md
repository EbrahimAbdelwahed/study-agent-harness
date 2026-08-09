# Study Agent Harness Context

This is the concise vocabulary and invariant sheet for the harness. The
approved behavior is defined by the accepted decisions in
[`docs/decisions/`](docs/decisions/) and the current implementation in
[`src/study_agent/`](src/study_agent/); this file names the boundaries without
duplicating their registries.

## Vocabulary

- **Harness** — the provider-neutral, local-first execution layer. It owns
  schemas, transitions, validation, replay, and trust boundaries; it is not a
  hosted product or a chatbot UI.
- **Host** — the embedding application that supplies a principal, repository,
  session, model adapter, and storage, and that bounds the adaptive loop.
- **Kernel** — canonical domain state and generic lifecycle rules: event
  append, projections, capability dispatch, validation, proposals, approvals,
  jobs, and observability.
- **Capability** — a versioned, discoverable study operation with schemas,
  policy, validators, provenance, idempotency, and explicit write permissions.
- **Tool** — a callable interface exposed to a host or capability. The current
  registry includes both queries and a bounded note command. The approved
  target keeps queries directly callable and routes new durable effects through
  permissioned capabilities and proposals.
- **Worker** — an execution component for a bounded capability. Workers do not
  own canonical policy or state; they return validated results or proposals to
  the kernel.
- **Source** — immutable, content-addressed learner material. A source
  revision, normalized substrate, citation, and derived knowledge-base
  projection have separate identities.
- **Evidence** — source-bound support that retains citation, lineage, and trust
  information. Candidate web evidence is quarantined until admitted.
- **Artifact proposal** — a versioned generated study artifact awaiting an
  explicit decision. Generation and validation never imply acceptance.
- **Reference Exam** — an immutable, approved authentic past exam or
  teacher-authored simulation used as evidence about assessment style. It is
  never reused as learner-facing generated content.
- **Exam Profile** — an approved, versioned description of assessment scope,
  topic mix, question types, detail, and phrasing, derived from a syllabus and
  compatible Reference Exams.
- **Generation Plan** — the learner-visible proposal describing what a
  Synthetic Verification will generate and why, without revealing its sealed
  questions.
- **Synthetic Verification** — a novel, sealed assessment generated from an
  approved Exam Profile and Generation Plan. Its questions become visible only
  during an attempt.
- **Decision Trace (approved target)** — the canonical minimal record of
  observable choices, outcomes, validators, and transitions. It is an audit
  trail, not model chain-of-thought.
- **Operational state** — checkpoints, indexes, job leases, metrics, and
  diagnostic payloads used for recovery or debugging. It is not canonical
  learner truth.

## Implemented invariants

1. The append-only event stream is canonical; projections, snapshots, and
   indexes are rebuildable and never independent authorities.
2. Models and providers propose or translate transport. They cannot select
   identity, permissions, policy, parentage, or canonical outcomes.
3. Skills and playbooks are model-independent. The host owns bounded adaptive
   choice; the kernel owns capability execution and validation.
4. Unknown, malformed, stale, unauthorized, or ungrounded input fails closed.
   Retries are bounded and never silently mutate canonical history.
5. Sources remain immutable and citable. Derived synthesis preserves claim
   lineage and trust and never becomes a primary source.
6. Generated artifacts remain proposals until an explicit authorized decision;
   generation and validation do not imply acceptance.
7. The kernel is dependency-light and model-neutral. It has no Pi/runtime
   dependency or vendored agent framework; hosts bring adapters and storage.
8. Provider-neutral service surfaces are asynchronous where execution can
   suspend. The reference SQLite adapter is local and single-writer; worker
   execution remains behind ports.
9. Stored execution proofs describe observable inputs, outputs, validations,
   and transitions; they do not request or store private chain-of-thought.
10. A single learner approval boundary is in scope. Cross-user sharing,
    organizations, billing, hosted operations, and product UI are deferred.

## Approved target constraints

- A sync convenience API must wrap the same async implementation; it must not
  become a second runtime.
- Synthetic Verification content remains sealed until an attempt, and required
  coverage gaps block release.
- A canonical Decision Trace will record the observable path taken. Full
  redacted payloads remain diagnostic-local operational data, retained for 14
  days by default, with no default remote telemetry.

## Source owners

Use the owning module or decision rather than copying its roster here:

- Domain values and event contracts: [`src/study_agent/domain/`](src/study_agent/domain/)
  and [ADR-0002](docs/decisions/ADR-0002--event-state-skills-playbooks.md).
- Host boundary and capability gateway: [`src/study_agent/application/`](src/study_agent/application/),
  [`src/study_agent/capabilities/`](src/study_agent/capabilities/), and
  [ADR-0004](docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md).
- Immutable knowledge-base identity and replay: [`src/study_agent/knowledge/`](src/study_agent/knowledge/),
  [`docs/specs/kb-v0-2-retrieval-architecture.md`](docs/specs/kb-v0-2-retrieval-architecture.md),
  and [ADR-0014](docs/decisions/ADR-0014--kb-v02-identity-compatibility-and-replay.md).
- Artifact and pedagogical policy: [`src/study_agent/artifacts/`](src/study_agent/artifacts/),
  [`src/study_agent/assessments/`](src/study_agent/assessments/), and
  [ADR-0008](docs/decisions/ADR-0008--closed-pedagogical-profiles-and-artifact-proposals.md).
- Provider and persistence adapters: [`src/study_agent/adapters/`](src/study_agent/adapters/);
  they remain technical boundaries, not behavior owners.

For the ordered future work, see [`ROADMAP.md`](ROADMAP.md). For ownership and
current-versus-target status, see [`CONTEXT-MAP.md`](CONTEXT-MAP.md).
