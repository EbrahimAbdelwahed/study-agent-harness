# ADR-0008: Closed pedagogical profiles and artifact proposals

Date: 2026-07-15
Status: Accepted

## Context

The adaptive tutor must generate grounded flashcards and other study artifacts
without turning one personal Anki pipeline into the OSS domain model. Two proven
flashcard methods exist locally: a general hierarchy-aware macro/detail method
and an anatomy-specific morphology-first method. They overlap on grounding,
parsimony, framework-first generation, and earned atomic details, but differ in
their retrieval jobs, density rules, and useful output structure.

Generated content must also remain a proposal. A model or generation service
cannot approve its own artifact, silently inherit acceptance across revisions,
or acquire canonical-write authority from prompt content.

## Decision

- Pedagogy is exposed through a closed, immutable, versioned profile catalog.
  The initial profiles are `hybrid-macro-detail@1` and
  `morphology-first-anatomy@1`.
- Profiles define retrieval roles, budgets, selection rules, prompts, and
  validator policy. They do not name providers, models, runtimes, deck names,
  Anki tags, credentials, or learner-wide preferences.
- The host selects a profile per bounded generation request. Explicit valid
  selection wins; otherwise `hybrid-macro-detail@1` is the default.
  `morphology-first-anatomy@1` requires explicit host selection grounded in the
  learner request or trusted material metadata. Course title heuristics and
  model output cannot select it.
- Profile selection is a typed host receipt containing the profile/version,
  `default | explicit_request | trusted_metadata` mode, trusted selector kind,
  and a basis reference. Default mode is valid only for hybrid. Morphology-first
  requires a learner-interaction or trusted-material reference. The receipt is
  supplied out of band from model output, is not prompt-authorable, and is
  persisted in proposal provenance.
- The shared artifact model is exporter-neutral. Flashcards store a retrieval
  form (`direct_recall | contextual_gap`), prompt, structured answer blocks,
  pedagogical role, rationale, grounded
  source commitments, lineage, and optional verified media references. Anki
  Basic/Cloze, HTML, decks, and tags are downstream mappings.
- One strict artifact envelope dispatches to kind-specific codecs for
  flashcards, assessment items, exam blueprints, and study briefs. Unknown kinds
  and unknown/extra fields fail closed.
- The other v1 content contracts are deliberately minimal and closed:
  `assessment_item` contains format, prompt, options, expected response, and
  evaluation criteria, but no attempt, grade, mastery, or schedule;
  `exam_blueprint` contains sample size, observed topic/format observations, and
  limitations, but no prediction presented as fact; `study_brief` contains a
  title, objective, bounded heading/summary/key-point sections, and limitations,
  but no learner model or schedule.
- Immutable artifact revisions begin `proposed`. Content never contains a
  decision. HUMAN may accept or reject; SERVICE may decide only through an
  injected, versioned, composition-root policy that returns a non-secret durable
  receipt. MODEL can never decide.
- Accepting a new revision explicitly names any previously accepted revision to
  supersede. Revision lineage and historical source commitments remain
  replayable.
- Generation capabilities return bounded verified proposal batches with empty
  state-write policy. The trusted application owner records proposals after
  verifying the run; capability output never commits acceptance.
- The public generated-proposal command accepts a run identity, never raw model
  content, success, or provenance. It retrieves a verified batch through an
  injected proof port. Direct authoring is a separate HUMAN-only revision path
  with learner interaction provenance; SERVICE and MODEL cannot use it.
- Revision provenance is a closed union. `generated` requires verified run,
  prompt, observed model receipt when used, validators, pins, output fingerprint,
  profile selection, read dependencies, and source commitments.
  `human_authored` requires HUMAN authority plus an exact existing human
  interaction, source commitments/read dependencies, and prior revision when
  revising; it forbids run/prompt/model/validator/output fields. Events and
  export preserve the origin discriminator.
- Optional artifact media uses a closed verified reference: trusted `BlobId`,
  lowercase SHA-256, source commitment index, non-secret verifier receipt
  id/version/fingerprint, and alt text. It is answer verification data, never an
  Anki filename or embedded markup.

## Profile Guidance for Tutor Hosts

Use `hybrid-macro-detail@1` for general medical lessons, mechanisms, sequences,
comparisons, and mixed material. Build a compact whole-source index, treat card
budgets as ceilings, create bounded framework cards before details, and add a
detail only for a fragile fact not recoverable from its parent.

Use `morphology-first-anatomy@1` for anatomical objects or regions whose useful
retrieval job is reconstruction of components, topology, relations, course,
profiles, or discriminating landmarks. Keep reconstruction cards dominant, add
at most three earned discriminations per macro, and use a contextual gap only
for compact relations or sequences. Media may verify recall only
when its blob identity and digest are trusted.

For mixed material, select one profile per bounded proposal batch or topic.
Do not merge both schemas into a permissive superset, and do not persist a
profile choice as a fixed learner trait. A profile version change produces a new
proposal revision rather than silently revalidating prior artifacts.

## Consequences

- Agents receive explicit, discoverable instructions without a rigid global
  workflow or provider-specific adapter.
- The general profile remains parsimonious and broadly applicable; it captures
  less anatomy-specific topology and media structure.
- The morphology profile supports spatial reconstruction and precise
  discriminations; it costs more schema/validation complexity and is unsuitable
  as the default for non-spatial mechanisms or narrative material.
- A closed catalog is less configurable than a generic pedagogy DSL, but it is
  testable, versionable, and safe to expose as an OSS compatibility surface.
- Downstream exporters must translate neutral artifacts into Anki or other study
  systems without changing canonical content or provenance.
- Existing export v1 bytes and file set remain unchanged for repositories with
  no artifact events. Artifact-aware export is an explicit deterministic v2;
  runtimes continue to replay old repositories. Neither version serializes
  credentials, principal IDs, idempotency keys, raw prompts, model response IDs,
  or private policy internals.
- Requesting export v1 for a stream containing artifact events fails closed with
  a stable `artifact export requires v2` error. V1 never silently drops artifact
  history and never changes its schema.

## Alternatives Considered

- Copy the personal Anki prompt and JSON format into the core: rejected because
  deck/tag/HTML/media conventions are product/export concerns.
- One configurable pedagogy DSL: rejected for v1 because it would expand the
  trusted behavior surface and make validators ambiguous.
- Infer morphology-first from course names or model classification: rejected
  because current course metadata has no trusted discipline field and model
  output cannot choose policy.
- Let successful generation auto-accept artifacts: rejected because validation
  proves shape and grounding, not learner intent or publication authority.
