# Adaptive Tutor

Status: Approved — implementation in progress
Last updated: 2026-07-20

## Next Agent Prompt

Read this README and the TUT-07 recall beads. TUT-04 through TUT-06 are
complete. The next adaptive-tutor core pickup is TUT-07A; the Build Week product
shell in TUT-08 is independently dependency-ready after TUT-06. Preserve the
per-course event stream as canonical, keep next-action selection in the
external tutor host, and do not add Anki behavior, arbitrary model memory, or a
global learner aggregate.

Global TODO:

- [x] [TUT-01 — progressive study context](slices/01-progressive-study-context.md)
- [x] [TUT-02 — tutor turns and snapshot](slices/02-tutor-turns-and-snapshot.md)
- [x] [TUT-03 — capability gateway](slices/03-capability-gateway.md)
- [x] [TUT-04 — study artifact proposals](slices/04-study-artifact-proposals.md)
- [x] [TUT-05 — assessment and learner evidence](slices/05-assessment-and-learner-evidence.md)
- [x] [TUT-06 — OpenAI reference tutor host](slices/06-openai-reference-tutor-host.md)
- [ ] [TUT-07 — recall and scheduling](slices/07-recall-and-scheduling.md)
- [ ] [TUT-08 — Build Week product shell](slices/08-build-week-product-shell.md)

## Goal

Enable an external agent to behave as a persistent adaptive tutor: it starts
from any learner request, uses the information already available, asks only
clarifications that matter to the current decision, invokes bounded study
capabilities, and adapts future work from replayable evidence.

The tutor is not a workflow in the core. The host chooses the next capability;
the harness owns trusted authority, typed state, validation, provenance,
idempotency, and recovery.

## Ubiquitous Language

- **Statement** — one structured fact explicitly declared by the learner.
- **Observation** — an immutable measured outcome such as an attempt or review.
- **Hypothesis** — a derived, evidence-linked and expiring interpretation; never
  a learner fact.
- **Proposal** — generated study content that has not been accepted.
- **Decision** — an explicit acceptance, rejection, resolution, or scheduling
  choice.
- **Capability** — one trusted versioned skill/playbook procedure that an agent
  may start or resume.
- **Tutor snapshot** — a sequence-consistent read model for the host; it does
  not prescribe a mandatory next action.

## State Model

### Canonical

The existing per-course append-only event stream records learner statements,
materials, session turns, artifact proposals and decisions, assessment items,
attempts, grades, reviews, and applied scheduling decisions. A generated claim
becomes canonical only as a record that the claim or proposal was produced;
the event does not make its content true.

### Derived

Rebuildable projections expose context conflicts, material and concept
coverage, performance by concept and assessment format, latency, confidence
calibration, retention evidence, and due work. Mastery and tutor hypotheses are
not canonical events.

### Operational

Agent focus, candidate actions, open dialogue checkpoints, model traces, and
tutor hypotheses live in bounded operational records. Losing them may reduce
continuity but cannot alter the canonical study history.

## Context Map

```text
Channel / UI
    -> Tutor Host (agent loop and capability choice)
        -> TutorSnapshotReader
        -> StudyCapabilityGateway
            -> StudyContext owner
            -> StudyArtifact owner
            -> Assessment owner
            -> Recall owner
                -> per-course event stream
                    -> deterministic projections
```

## Architectural Decisions

1. The tutor host, not the core, owns autonomous planning and selection of the
   next capability.
2. The first release is single-learner and course-scoped. Cross-course learner
   identity and modeling require a separate future decision.
3. Progressive context uses a closed statement vocabulary, not arbitrary
   key/value memory or a model-authored biography.
4. Contradictory scalar statements remain visible until explicitly resolved.
   They are never silently overwritten by recency.
5. Skills and playbooks remain the behavior layer. Playbooks are bounded,
   suspendable procedures, not a global onboarding funnel.
6. Study artifacts are proposed, revised, accepted, rejected, or superseded.
   Generated content cannot implicitly approve itself.
7. Attempts are canonical before grading. Free-text grades record a versioned
   evaluator outcome with rubric, citations, confidence, and provenance.
8. Learner evidence is a replayable projection whose estimates name their
   supporting and contradicting evidence.
9. Applied scheduling decisions are recorded with policy version and input
   fingerprint because they change future tutor behavior.
10. API-key and subscription experiences are separate tutor-host adapters over
    the same core contracts.
11. Flashcard generation is lesson-scoped but worker-bundled: deterministic
    global index, coherent non-overlapping paragraph/topic bundles, fresh
    provider-neutral worker contexts, and parsimony without a lesson card quota.

## Compatibility

The existing seven `agent-operations@1` StudyTools and their fingerprints stay
unchanged. Adaptive capabilities are advertised through a new versioned
capability contract; they are not smuggled into the old closed tool set. New
event schemas are additive and existing v1 course, source, and session replay
must remain valid.

## Dependency Graph

```text
TUT-01 progressive context
  -> TUT-02 tutor turns and snapshot
      -> TUT-03 capability gateway
      -> TUT-04 artifact proposals
          -> TUT-05 assessment and learner evidence
              -> TUT-06 OpenAI reference host
                  -> TUT-08 Build Week product shell
              -> TUT-07 recall and scheduling
```

TUT-03 and TUT-04 may proceed in parallel after TUT-02 if their integration
files are isolated. TUT-06 and TUT-07 may proceed in parallel after TUT-05.
TUT-08 depends on the reference host, not recall; it exposes recall only when
TUT-07 is present.

## Global Acceptance Criteria

- A learner can begin a session without a complete study goal.
- Missing context is reported but never forces a fixed onboarding order.
- Inferred information cannot enter canonical learner statements.
- Conflicting learner statements are replayable and visible.
- The host may select any currently authorized capability without changing the
  core or provider adapter.
- Capability interruption never commits an incomplete result as successful.
- Generated artifacts retain source and execution provenance and remain
  proposals until a decision accepts them.
- An assessment attempt commits before any generated grade.
- Learner evidence and tutor snapshots rebuild byte-identically from the same
  event schemas and reducer versions.
- Model, agent SDK, UI, and provider imports remain outside domain, state,
  skills, playbooks, and application owners.
- Offline scripted-model tests remain the default; network tests are opt-in.
- Existing lifecycle, replay, export, CLI, and exact seven-tool contracts stay
  green.
- Main tutor traces contain compact generation summaries rather than raw lesson
  evidence, worker scratch output, or detailed candidate pages.

## Non-goals

- Generic autonomous planning inside the core.
- Arbitrary long-term model memory or fixed learning-style classification.
- Multi-user auth, tenancy, collaboration, or cross-course learner state.
- Dynamic or untrusted skill installation.
- PDF/OCR/audio, vector retrieval, hosted sync, calendar integration, or
  `sbobby-web` changes.
- Repository-wide transactions or manifest authority over study behavior.

## Verification Strategy

- Unit: strict value/event codecs, conflict resolution, artifact and assessment
  lifecycle, scheduling policy, and deterministic estimators.
- Contract: capability manifests/outcomes, projection views, provenance, safe
  errors, and host authority.
- Integration: free-form entry, progressive context, explanation, test,
  attempt-before-grade, evidence update, artifact decision, and replay.
- Evals: minimal clarification, direct action with incomplete context, changed
  learner intent, unsupported grading, and interrupted capability recovery.
- Architecture: provider/agent/UI imports remain outside core owners and the
  v0.1 seven-tool registry remains unchanged.
- Release: Python 3.12/3.13, Ruff, strict mypy, clean wheel, deterministic
  offline demo, and opt-in GPT-5.6 smoke.

## Grilling Evidence

The architecture was checked against the current immutable `CourseProfile`,
course-scoped event sequence/CAS, general session limitations, sequential
playbook suspension, exact seven-tool registry, source roles, answer
provenance, export allowlist, and ADR-0002. Resolved decisions:

- progressive facts belong to a new course-scoped context owner rather than
  mutable course metadata;
- dialogue suspension is a capability-local primitive, not global tutor flow;
- exam samples reuse source roles but require a separate artifact blueprint;
- mastery remains derived and evidence-linked;
- pre-course and cross-course tutor memory stay outside this release;
- Build Week fully implements the API-key reference host and documents, but
  does not fake, subscription equivalence.

## Build Week Cut Line

TUT-01 through TUT-06 must ship. TUT-07 should ship with one deterministic
review policy if time permits. TUT-08 contains only the thin conversation-first
consumer, evidence panels, demo fixture, eval report, and submission-quality
documentation. TUT-04F must prove the same lesson/exam flows headlessly before
TUT-08 binds a UI to them.
