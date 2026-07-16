# ADR-0010: Lesson-scoped isolated generation workers

Date: 2026-07-16
Status: Accepted

## Context

The first TUT-04C draft treated one prepared scope as one model call and exposed
a hard maximum of 24 candidates without defining the pedagogical unit to which
that number applied. That shape is safe as a transport bound but weak as a study
method: a lesson can contain a few large frameworks or many short sections, so a
fixed lesson card target encourages quota filling or arbitrary compression.

The proven `Audio_to_Sbobina` method uses one lesson as the outer generation
unit, constructs a deterministic global heading index, and sends only contiguous
active topic bundles to generation. The refined implementation in
`scripts/repair_embrio04_10_quality.py` and
`dev/notes/2026-06-27-2230--anki--hierarchical-card-prompt-design--note.md`
keeps the compact whole-lesson index visible while limiting factual evidence to
the active bundle. It generated overview/framework cards before selective
details and aggregated the lesson only after all bundle calls.

The external tutor also needs generation details not to consume or contaminate
its conversational context. Skills and playbooks must preserve that isolation
without depending on an OpenAI-, Anthropic-, DeepSeek-, or SDK-specific
"subagent" primitive.

## Decision

1. A **lesson generation unit** is one trusted host-defined ordered source scope.
   It normally represents one consolidated lesson; supplemental sources may be
   linked explicitly, but the core does not infer lesson membership.
2. Before any generation, a deterministic planner builds a versioned lesson
   index containing topic identity, title, level, parent, canonical source span,
   visible size, order, and trusted planning classification. The index is
   bounded to 256 entries and fails explicitly rather than truncating.
3. Generation uses ordered, non-overlapping bundles of contiguous topics. The
   default policy targets approximately 5,000 visible source characters per
   bundle. Heading/subtree boundaries are preferred; an oversized topic is split
   only at whole paragraph boundaries. The threshold is a versioned soft
   operational limit, not a semantic boundary. Each bundle also contains at most
   24 planned evidence slots so it can resolve without loss into the existing
   bounded evidence envelope.
4. Every bundle worker receives the compact global lesson index for scale and
   navigation, but only the active bundle's verified evidence may support factual
   output. No transcript overlap or duplicated paragraph span is copied into
   adjacent bundle evidence.
5. Each bundle runs as an **isolated generation worker** with a fresh model
   request. It receives only an allowlisted task envelope: pinned prompt layers,
   global index, active evidence, explicit learner preferences, and a bounded
   canonical continuation summary. Tutor message history, other raw materials,
   credentials, principal data, and prior worker scratch output are absent.
6. The isolated worker is expressed through provider-neutral playbook/model
   contracts. A provider adapter may implement the fresh request with a native
   subagent facility, but no provider-specific agent abstraction enters the core.
   A generic worker wrapper starts/resumes one complete child capability/playbook
   run; the profile playbook's single `ModelStep` is the only model effect.
7. The refined generation order is optional lesson overview first, then section
   frameworks followed by their earned details within each active bundle.
8. Card count is governed by parsimony: frameworks that support reconstruction
   and fragile facts that fail recoverability may produce cards; scaffolding,
   repetition, general knowledge, and derivable details may produce none. There
   is no default lesson card target and no minimum.
9. The existing 24-candidate bound remains a hard per-worker transport and
   review-page ceiling only. It is never presented to the worker as a desired
   count. A lesson may span multiple verified child runs/pages.
10. A durable operational coordinator fingerprints the plan, derives child
    retry identities, records completed child run IDs, and resumes from the first
    unfinished bundle without repeating successful workers. The tutor receives a
    compact coverage/omission summary; detailed drafts and evidence remain behind
    typed views for UI/review consumers.
11. Cross-bundle aggregation preserves order and fails closed on duplicate,
    overlapping, unsupported, or incompatible candidates. The core does not
    silently apply fuzzy deletion.
12. Trusted planning uses `eligible|context_only|excluded`; model-authored
    profile dispositions use a separate vocabulary. A model may omit eligible
    material but cannot elevate context-only, excluded, or inactive topics.
13. Planned bundle metadata crosses the preparation boundary through a new
    strict `PreparedPlannedFlashcardScope` wrapper. It contains the unchanged
    `PreparedFlashcardScope` plus plan/bundle/topic/classification commitments;
    the existing preparation tool and canonical bytes are not widened in place.

## Consequences

- C1 and C2 operate on one active lesson bundle, not an entire lesson-sized raw
  prompt, and depend on shared planning and worker-runner prerequisites.
- C3 owns composition of the planner, isolated child runs, resume, aggregation,
  and profile-stable gateway behavior.
- Large lessons can continue without inventing a pedagogical card quota.
- The main tutor context stays small and does not inherit generation scratch
  work or raw lesson evidence.
- The historical 14–22 ranges, 62% section allocation, Casasco regexes,
  mandatory per-topic output, Anki fields, and fuzzy auto-deduplication are not
  copied.
- Future GEPA calibration can use source spans, prompt fingerprints, generated
  candidates, human decisions, and learner outcomes without retaining private
  reasoning traces.

## Alternatives Considered

- One model call for the whole lesson: rejected because it causes context/output
  bloat and gives every paragraph similar local weight.
- One call per paragraph without a global index: rejected because it creates
  local overcoverage and loses lesson-scale hierarchy.
- A fixed number of cards per topic or lesson: rejected because topic size and
  recoverability vary materially.
- Provider-native subagent APIs in the core: rejected because they would violate
  the model- and agent-agnostic boundary.
- Silent fuzzy deduplication after generation: rejected because it is not
  replay-safe enough to decide which study artifact survives.
