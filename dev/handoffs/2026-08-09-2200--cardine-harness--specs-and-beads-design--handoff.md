# Handoff: Cardine / Study Agent Harness specs and beads design

Date: 2026-08-09 22:00
Area: Cardine, Study Agent Harness, package adoption, future implementation specs

## Current State

The user requested an overlap analysis between Cardine and Study Agent Harness,
followed by four execution-ready implementation specs and dependency-aware task
beads. The work is still in the grilling/decision-closure phase. No specs or
beads have been written yet.

The overlap analysis must use these documents as its semantic sources:

- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/CONTEXT-MAP.md`
- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/TECHNICAL-MAP.md`
- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/docs/domain/*/CONTEXT.md`
- Harness `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT.md`
- Harness `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT-MAP.md`

Do not use old specs or beads as authority for the semantic overlap. They may
be inspected later as historical implementation material after ownership and
contracts are fixed.

## Skills and Process

- The active interview follows
  `/Users/ebrahimabdelwahed/.codex/skills/grilling/SKILL.md`.
- Spec materialization must follow
  `/Users/ebrahimabdelwahed/.codex/skills/write-spec/SKILL.md`.
- Beads and worker briefs must follow the dedicated repo-local skill and its
  templates:
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/skills/implementation-orchestrator/SKILL.md`
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/templates/task-bead.md`
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/templates/worker-brief.md`
- Every bead must be executable without redesign or TBDs, fit one fresh context,
  produce an observable independently verifiable outcome, name spec coverage
  and grilling evidence, and declare worker profile, context, allowed scope,
  acceptance criteria, verification, dependencies, and out-of-scope behavior.
- Wide migrations use `expand -> migrate -> contract`; every temporary seam has
  an explicit removal bead.
- The user wants all architecture questions resolved before bead creation; do
  not create architecture-closure beads.

## Approved Four-Spec Structure

Exactly four main specs will be created:

1. Harness — Package Foundation.
2. Cardine — Harness Adoption.
3. Harness — Future Runtime Features.
4. Cardine — Future Product Features.

Each spec lives in its owning repository and contains its own slices/beads.
There is no fifth cross-repository spec. Cross-repository dependencies are
unidirectional:

```text
Harness contract bead -> released package/contract version -> Cardine adapter bead -> Cardine product bead
```

Harness must never depend on Cardine.

## Approved Ownership Boundary

- Harness owns provider-neutral mechanisms and portable contracts.
- Cardine owns academic meaning, product policy, composition, UI, auth, and
  deployment.
- Harness owns immutable source identity/revisions/blob/citation mechanics;
  Cardine owns educational authority, currency, integrity, notices, and
  curriculum alignment.
- Harness owns generic artifact proposal/revision/decision lifecycle; Cardine
  owns artifact kinds, approval policy, substantial-revision meaning, and
  product effects.
- Harness owns portable Reference Exam, Exam Profile, Generation Plan, and
  Synthetic Verification schemas/workflow; Cardine owns academic authenticity,
  exam components, attempts, criteria, grades, contests, and profile approval.
- Harness owns generic recall ledger, scheduling port, and due view; Cardine
  owns eligibility, rating meaning, substantial-revision effects, and mapping
  Retention Observations into Learner Model inputs.
- Cardine is the only planner. It owns Study Plan, Next Activity, rationale,
  mastery/readiness use, and learner overrides. Harness only validates and
  executes the selected bounded capability.
- Curriculum and Learner Model remain entirely Cardine-owned. Harness accepts
  opaque typed references such as concept, objective, and profile revision IDs.
- Domain Events are Cardine/product facts. Decision Trace is separate execution
  audit evidence. They link by correlation/causation IDs; no duplicate fact and
  trace does not feed mastery/domain projections.
- Shared contracts must not use bare `Evidence`: use `SourceEvidence`,
  `LearningEvidence`, `RetentionObservation`, and `CandidateWebEvidence`.

## Approved Package Direction

- Cardine will consume a versioned Study Agent Harness package; it will not keep
  an independently evolving copied core or a maintained source mirror.
- Harness retains the `study_agent` Python namespace exclusively.
- Cardine product code moves to `cardine`.
- Cardine imports Harness only through an anti-corruption/integration layer,
  recommended location `cardine.integrations.study_agent`; Cardine domain/UI/API
  expose Cardine DTOs rather than raw Harness objects.
- Cardine consumes stable library APIs only, not Harness CLI/browser/reference
  host composition.
- Migration order: Package Foundation -> Cardine adapter -> deterministic parity
  -> debug data reset -> copied-core removal -> future feature lanes.
- The Package Foundation stabilizes already-existing shared behavior only.
  Job kernel, workers, Decision Trace, web evidence, and sealed verification are
  Spec 3 and must not block removing the copied core.
- During adoption Cardine pins an exact package version/lock. After parity it may
  use a same-major compatible range, with every Harness upgrade represented by
  a verified Cardine bead.
- Semantic Versioning policy approved: curate an explicit public facade during
  `0.x`; release `1.0.0` after stable API/parity; thereafter MAJOR may break,
  MINOR is compatible functionality, PATCH is compatible bugfix.

## Approved Package Foundation Contracts

- Public API is a curated `study_agent.api` facade with typed subfacades for
  runtime, authority, storage ports, sources/citations, capabilities, artifacts,
  assessments, and recall. Root `study_agent` exposes version/facade only;
  internal modules have no SemVer guarantee.
- Composition is explicit dependency injection. Cardine/Host supplies principal,
  repository, storage, clock, ID factory, model adapter, and policy. No global
  locator, singleton, or hidden auto-configuration.
- Events use a versioned envelope containing event ID/type/schema version,
  aggregate or stream ID, timestamp, causation/correlation IDs, and validated
  payload. Deterministic upcasters can read supported old versions.
- Public failures use a typed closed taxonomy: validation, stale, unauthorized,
  conflict, not found, unavailable dependency, and internal failure. Provider,
  SQLite, and filesystem exceptions do not leak through the facade.
- Durable commands require idempotency keys. Same key/same input converges; same
  key/different input conflicts. Cancellation is cooperative before commit;
  committed events are not rolled back; retry occurs only from declared
  checkpoints.
- Capability/plugin registration is explicit, namespaced, manifested,
  permissioned, and versioned. No import-time/entry-point auto-discovery.
- Base package has no mandatory runtime dependencies beyond the standard
  library. SQLite remains built-in; provider, FSRS, OpenTelemetry, and specialist
  integrations are optional extras/adapters.
- Cardine registers product events/reducers/projections/services through an
  explicit immutable `KernelModule`. Collisions, unknown schemas, and late
  registration fail closed. Harness never imports Cardine.
- Ports are the main compatibility contract. Narrow first-party SQLite,
  filesystem blob, clock, and ID adapters are supported/documented consumers.
  Cardine owns paths and composition.
- Only the Host creates principals/grants/scopes: authenticated owner is HUMAN,
  authorized Cardine policy is SERVICE, provider is MODEL and can never approve.
  Cookies and browser credentials remain outside Harness events/DTOs/traces.
- Cardine deletes old `study-agent*` CLI aliases; only Harness owns those names.
  Cardine exposes only `cardine*` commands.
- Cardine product events and Harness-owned portable events share one per-course
  event store/sequence through KernelModule registration. Decision Trace is
  stored separately.
- Foundation release gates: clean wheel/sdist installs on Python 3.12/3.13;
  public import-manifest test; base dependency-free install; Ruff, strict mypy,
  full offline suite; reusable event/blob/replay/capability contract kit; no
  Cardine refs/product/auth/UI; simultaneous Harness+Cardine installation has no
  file or entry-point collision.
- Distribution direction approved: tagged PyPI wheel/sdist, first adoption
  release recommended as `0.3.0`, exact Cardine pin during adoption, `1.0.0`
  after parity/stabilization. CI installs the built/published artifact, never a
  sibling checkout or PYTHONPATH injection.

## Approved Cardine Adoption Contracts

- Use `expand -> migrate -> contract`:
  1. create `src/cardine` and new entry points;
  2. migrate composition root/UI/auth/settings/product behavior in green
     vertical slices;
  3. remove all temporary shims and Cardine-owned `study_agent` modules after
     import and parity gates pass.
- No external compatibility promise for old Cardine `study_agent` imports or
  `study-agent*` CLI aliases.
- Every copied/divergent file must be classified as: import from Harness; move
  to Cardine; upstream generic delta first; or temporary adapter with an explicit
  removal bead. No copied shared file remains at the end.
- Behavioral parity, not byte equality, is required before removal: same replay,
  identity/lineage, citation resolution, session/continuation recovery,
  artifact/assessment/recall outcomes, semantic export, and fail-closed stale/
  invalid/unauthorized behavior. UI may change without losing functionality.
- Existing Cardine canonical state is only debugging data and need not be
  migrated or preserved. There is no state migrator and no canonical dual write.
- Reset automatically removes known Cardine runtime data without pausing for
  user confirmation. The implementation resolves and validates exact targets
  first, then removes canonical, derived, and operational debug data while
  preserving versioned fixtures/code and original external source files.
- Known repository data paths from the audit are `study-agent.json`,
  `state/events.sqlite3`, `state/runs.sqlite3`, `state/retrieval.sqlite3`,
  `blobs/`, and `exports/`. Blob deletion destroys internally imported source
  content, which is authorized because this repository state is disposable.
- Do not keep a permanent broad destructive `reset --all` command merely for
  this migration.
- No implementation-time confirmation is allowed for the authorized debug-data
  reset; it must not block the agent.

## Verified Code Facts

- Harness distribution is `study-agent-harness` v0.2.0 and Cardine distribution
  is `cardine` v0.2.0.
- Both currently install the same regular top-level package `study_agent`, so
  side-by-side wheels collide.
- Cardine adds product tutor, Luna, UI/auth/settings, continuation/handoff, and
  diagnostics modules, while lacking multiple Harness KB v0.2 modules.
- Existing parity tests are intra-tree, not cross-distribution install/parity
  tests.
- `LocalRepository` is the current composition seam in both projects.
- Both share event/blob/run/retrieval repository layout; Cardine also stores tutor
  continuation/handoff operational data in `runs.sqlite3`.

## Remaining Decision Frontier

The decision frontier is empty. Package Foundation, Cardine Adoption, Harness
Future Runtime, and Cardine Future Product have no remaining user-level design
decisions. The only remaining grilling action is explicit user confirmation of
the shared-understanding summary before materializing specs and beads.

## Approved Harness Future Runtime Contracts

- One outer Job lifecycle replaces parallel worker/lesson lifecycle ownership:
  `QUEUED -> RUNNING -> SUSPENDED | SUCCEEDED | FAILED | CANCELLED | STALE`.
  Lease is RUNNING metadata; retry creates a new attempt under the same Job;
  playbook checkpoints remain subordinate execution proofs.
- Job/lease/heartbeat/attempt/queue data is durable operational state in a
  separate JobStore. Only a domain owner can commit a canonical outcome.
- Workflow identity derives from capability/version, authority scope,
  idempotency key, and input fingerprints; child jobs derive from parent,
  position, and task fingerprint; attempts are monotonic. Same identity with
  different bytes conflicts.
- Defaults: 60s lease; 20s heartbeat; expired lease requeues with increasing
  fencing token; global and per-workflow concurrency 8; hierarchy depth 1;
  maximum 64 child jobs; FIFO deterministic claims; at-least-once execution and
  exactly-once canonical commit through owner idempotency.
- Retry defaults: maximum 3 attempts; 1s/2s/4s exponential backoff with +/-20%
  jitter and 30s cap; only timeout/rate-limit/provider-5xx/declared-transient
  failures retry. Validation, authorization, integrity, conflict, and stale do
  not. Cancellation completes at safe points without canonical rollback.
  Suspended jobs hold no lease; resume tokens bind job/attempt/checkpoint/
  authority/input/dependencies and conflicting response bytes fail.
- Decision Trace is a separate append-only stream with trace/workflow/job/
  attempt/capability, correlation/causation, transition, validators/outcomes,
  safe error, fingerprints, and timestamps. It excludes full prompts, excerpts,
  outputs, secrets, raw personal identity, and chain-of-thought. Minimal trace
  lasts until repository deletion; redacted diagnostic payloads last 14 days;
  optional OpenTelemetry loss never changes execution.
- Flashcard planner/coordinator/leaf/reviewer/assembler run as Jobs. Each leaf
  sees one evidence cluster and produces at most 6 candidates under a declared
  context budget. Partial proposals require visible missing clusters/failures;
  no silent omission or automatic acceptance. Reducers inspect candidates,
  rubrics, fingerprints, coverage, and references, fetching source spans only
  for targeted conflicts. Specialized lifecycle stores are removed after parity.
- WebEvidencePort is provider-neutral; scripted offline connector is mandatory;
  first optional live adapter is OpenAI Responses web_search; no arbitrary
  direct URL fetch in v1 and no live adapter in base core.
- Web defaults: at most 8 queries/workflow, 10 candidates/query, 45s timeout,
  256 KiB extracted text/candidate, HTTPS references only, no cookies/
  credentials/active execution, untrusted connector output, 7-day candidate
  retention, and explicit partial result on network failure.
- Broker cannot admit evidence. HUMAN or injected trusted SERVICE admits an
  exact snapshot; receipt records hash, URL, timestamp, connector, query,
  provenance, policy/version, and decision. Admitted content becomes immutable
  Source Revision; synthesis never becomes a primary source.
- Harness owns portable ReferenceExamRef, ExamProfile, GenerationPlan,
  SyntheticVerification, and CoverageReport lifecycle schemas with opaque host
  academic refs. Sealed means application authority, not claimed encryption.
  Student sees an accepted plan and progressive questions only during attempt;
  answers after finalization. Lists/search/export/trace/errors never leak sealed
  content.
- Verification lifecycle: approved profile + accepted plan -> generation Jobs
  -> independent coverage reviewer -> deterministic release gate ->
  presentation. Generator cannot self-review/release; any required missing,
  partial, or uncertain coverage blocks release.
- Novelty: normalized exact match regenerates; 5-token-shingle Jaccard >=0.75
  regenerates; 0.55-0.75 is uncertain and regenerates; two failed regenerations
  suspend without exposing content to the learner.
- Every generated question pins profile, plan, sources, scope/objective refs,
  prompt/worker/validator versions. Drift stales only affected shards;
  regeneration creates a new revision and reruns global review; prior attempts
  remain historical. Harness returns presentation receipt; Cardine owns attempt,
  response, grade, and contest.
- Offline gates: 100% schema/authority/citation/sealed-leak checks; 100% required
  coverage; zero unsupported claims; reviewer macro-F1 >=0.95; deterministic
  replay equality. Live opt-in candidates compare with an exact Luna baseline;
  critical capability promotion requires no critical failures and quality
  within 3 percentage points. Cost/token/latency are reported separately.
- Release waves: Job+Trace -> Flashcard Jobs -> Web Evidence -> Sealed
  Verification -> Eval/package release.

### Closed Cardine Future Product decision checklist

1. Curriculum concept/objective IDs, revisions, and activation.
2. Graph relation vocabulary, acyclicity, propagation, and objective axis.
3. Alignment admission and syllabus backbone/conflict behavior.
4. Educational Authority/Currency/Integrity contracts and official-syllabus
   discovery.
5. Conversation cardinality and Study Session linkage.
6. Assistance Context and Evaluative Turn exact fields/preconditions.
7. Reference Exam/Question identity and Exam Profile composition/activation.
8. Synthetic verification integration, criteria, authenticity, prior exposure,
   and grade-contest effects.
9. Versioned deterministic Evidence Strength policy and golden vectors.
10. Mastery scale, temporal model, contradictions, and graph propagation.
11. Readiness aggregation, coverage/confidence, critical-gap thresholds.
12. Estimate rebuild/cache keys and explanation contract.
13. Substantial artifact revision classification and RetentionObservation types.
14. Study Plan aggregate and deterministic NextActivity algorithm.
15. Provider consent, secret blocking, retention/export/delete policy.
16. UI truth contract, sealed-content leak prevention, deterministic vs Luna
   responsibilities, and product eval gates.
17. Final dependency ordering between product lanes.

## Approved Cardine Curriculum, Tutoring, and Exam Contracts

- ConceptId and LearningObjectiveId are opaque, course-scoped, text-independent
  IDs created by an injected ID factory. Curriculum revisions are immutable;
  one revision is active per course; activation requires authorized HUMAN or
  injected SERVICE decision and never rewrites historical evidence.
- Curriculum relation vocabulary v1 is closed: `IS_PART_OF` is an acyclic
  multi-parent hierarchy; `REQUIRES` is independently acyclic prerequisite;
  `RELATED_TO` is symmetric and non-propagating. Only IS_PART_OF may contribute
  to attenuated roll-ups. Objectives are course-scoped/versioned on a separate
  axis; alignments pin revision, concept, and objective.
- Curriculum activation requires an approved official syllabus. Sources/exams
  may propose nodes/relations but cannot remove syllabus requirements. All v1
  generated alignments require HUMAN approval; confidence/provenance alone
  grants no authority; unresolved conflict blocks activation.
- EducationalAuthority values: OFFICIAL_SYLLABUS, LECTURER_MATERIAL,
  REFERENCE_TEXT, LEARNER_NOTE, ADMITTED_WEB, OTHER. SourceCurrency values:
  CURRENT, PARTIAL_MATCH, OUT_OF_PERIOD, UNKNOWN, derived deterministically
  from academic period, lecturer, and syllabus. SourceIntegrity is separate:
  VERIFIED, FAILED, UNKNOWN.
- Syllabus discovery is user-triggered through WebEvidenceBroker; candidates
  remain quarantined until learner admission; no periodic search or automatic
  replacement.
- One durable Conversation per course in v1 spans many bounded StudySessions.
  Sessions record intent/activity/start/end/outcome. Browser/auth sessions are
  unrelated. Model context uses a bounded projection, never the full dialogue.
- AssistanceContext records visible sources, available history, hints, guided
  steps, open-book state, time, previous exposures, and model assistance.
  EvaluativeTurn fixes assessment intent, criteria, content scope, objective,
  assistance policy, and contract fingerprint before the answer. Ordinary
  conversation cannot be promoted retroactively into LearningEvidence.
- ReferenceExam revision pins immutable SourceRevision; ReferenceQuestion has
  stable exam-local ID and exact citation; extraction is a proposal and HUMAN
  approval grants authenticity; attempts record prior exposure.
- One ExamProfile is active per exam regime. It contains only the components
  that actually exist (e.g. written, oral, practical or another declared
  component); it does not require all three. Weights of active components must
  sum to 1. It also owns coverage targets, criteria, and critical requirements;
  incompatible reference exams are not merged automatically.
- Cardine approves ExamProfile and GenerationPlan, invokes Harness, and records
  presentation receipt; Cardine owns attempt/grading. Criteria are fixed before
  response; authenticity, profile compatibility, assistance, and prior exposure
  remain separate. A contested grade remains factual history but has zero
  Learner Model weight until confirmed, replaced, or invalidated; original
  history is preserved.

## Approved Cardine Learner Model, Planning, Privacy, and UI Contracts

- Evidence Strength policy v1 is deterministic/versioned. Base values:
  compatible Reference Exam 1.0; Synthetic Verification 0.9; Evaluative Turn
  0.7; scored delayed retrieval 0.6; self-rated review 0.2. Multipliers:
  compatibility exact/partial/incompatible = 1/0.6/0; assistance closed/open-
  book/hint/guided = 1/0.8/0.6/0.4; exposure unseen/seen/repeated = 1/0.7/0.4;
  alignment approved criterion+scope+objective/scope-only/absent = 1/0.6/0;
  recency half-life 90 days with 0.25 floor; contested grade = 0. Strength is
  clamped product. These are an executable v1 baseline, explicitly expected to
  be tuned later using real data through a new policy version and eval evidence,
  never an implementation-time TBD.
- Mastery is per exact curriculum-revision/concept/objective. Outcome is 0..1;
  evidence mass is summed strength; estimate is weighted outcome mean;
  disagreement is weighted mean absolute deviation; confidence is
  `(1-exp(-mass/3))*max(0,1-2*disagreement)`. Insufficient when mass <1.5 or
  fewer than two independent sessions, except one compatible Reference Exam
  with strength >=0.9. No graph propagation mutates mastery; parent roll-ups are
  separate views using IS_PART_OF and explicit importance weights.
- Readiness per requirement uses 0.6 direct compatible performance + 0.4
  mastery when direct evidence exists, otherwise mastery. Coverage is weight of
  sufficiently evidenced requirements; confidence is weighted confidence times
  coverage; a critical requirement with insufficient evidence or score <0.6 is
  a Critical Gap. Status thresholds: coverage <0.70 or confidence <0.60 =>
  INSUFFICIENT; score <0.60 => NOT_READY; 0.60-0.79 => DEVELOPING; >=0.80 with
  no Critical Gap => READY. Only active exam-component weights, summing to 1,
  contribute. These constants are also versioned/calibratable baselines.
- Mastery/readiness projections key on event high-water, curriculum revision,
  exam-profile revision, policy version, and as-of day. Explanations expose
  supporting/contradicting evidence, strength, limitations, coverage,
  confidence, and state rationale. Browser/model never computes them.
- Flashcard changes to prompt, answer, cloze, evidence scope, or profile are
  substantial; typo/whitespace/equivalent formatting are not; ambiguous cases
  require HUMAN decision. Accepted substantial revision creates a new enrollment
  consideration and does not inherit schedule; old history is frozen.
  RetentionObservation is SELF_RATING or SCORED_RETRIEVAL with card revision,
  time, assistance, and interval. Recall emits facts; Learner Model interprets.
- One ActivePlan/course owns constraints, milestones, workload, deadline,
  exam/profile refs, and revision diff; HUMAN acceptance is required and
  pending/rejected proposals do not modify it. NextActivity candidate score is
  urgency 0.30, critical gap 0.25, learning gap 0.20, due recall 0.15, learner
  preference 0.10, after hard constraints for time, prerequisites, eligibility,
  and ActivePlan. Tie-break is deadline, stable type, ID. Output includes one
  recommendation, alternatives, and trade-off; learner override does not revise
  the plan implicitly. Weights are versioned/tunable baselines.
- Consent is canonical/versioned per provider, transmission class, and source
  scope. Recognized secrets always block; other sensitive signals warn and
  require confirmation for the scope/version. Revocation blocks future calls
  without rewriting history. Export includes attributable canonical facts and
  versioned estimates, with trace separate and caches/jobs excluded or marked
  operational; diagnostic payloads expire after 14 days. Repository deletion
  deletes all and is distinct from adoption debug reset.
- UI exposes proposal state/provenance/as-of/coverage/confidence and never renders
  INSUFFICIENT as low ability. Sealed content cannot leak through list/search/
  export/error/trace. Luna may propose alignments, profiles, plans, and
  explanations. Graph validity, Evidence Strength, mastery/readiness, activation,
  ranking, constraints, and approvals are deterministic.
- Product gates: deterministic policy/replay/leak/adversarial fixtures 100%;
  Luna schema and citation validity 100%, zero critical errors, rubric pass
  >=90%; alternative model promotion requires no critical error and quality
  within 3 percentage points of exact Luna baseline.
- Product dependency order is curriculum IDs/source semantics -> alignments ->
  Reference Exams/Profile + Assistance Context -> LearningEvidence/
  RetentionObservation -> Learner Model -> Study Plan/NextActivity -> integrated
  UI. Artifact substantial-revision work may start after adoption; syllabus
  discovery depends on Harness Web Evidence; Synthetic Verification depends on
  its Harness release.

## Interview Status

All four accelerated decision rounds are complete. Do not re-ask approved
decisions. Present a compact shared-understanding summary and request the one
final confirmation required by the grilling skill before writing specs/beads.

## Important Invariants

- One owner per concept, state machine, persistence record, and policy.
- Cardine never redefines a portable Harness contract.
- Harness never imports Cardine or computes curriculum, mastery, readiness, or
  planning.
- Model output remains untrusted and cannot acquire authority.
- No compatibility bridge survives its last consumer.
- No canonical dual write or duplicated event for one fact.
- Jobs, diagnostics, caches, and traces never become learner truth.
- Sealed material cannot leak through list, search, export, trace, errors, or UI.
- Every numeric policy/threshold must have versioned golden test vectors.
- Offline verification remains a complete release path.

## Next Action

Resume with the fast four-round interview described above. When the frontier is
empty, ask the user to confirm shared understanding. Only after confirmation:

1. create the four specs using `write-spec`;
2. use at least three differently biased drafting agents as required by that
   skill, then synthesize;
3. run `refactor-clean` over the materialized specs;
4. use `implementation-orchestrator` to create executable beads, dependency DAG,
   profile decisions, and initial worker briefs;
5. verify no bead contains `decide`, `choose`, `TBD`, or hidden redesign work.
