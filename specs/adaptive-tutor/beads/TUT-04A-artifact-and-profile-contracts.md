# Task Bead: TUT-04A artifact and pedagogical-profile contracts

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-02

## Outcome

Provider-neutral domain contracts define strict study-artifact content,
immutable revision/provenance identities, and a closed discoverable catalog for
the general hybrid and anatomy morphology-first flashcard profiles.

## Acceptance Criteria

- [x] Artifact, revision, batch, and profile identities are typed and
  deterministic; no model-authored candidate key becomes canonical identity.
- [x] One envelope dispatches to exact versioned codecs for flashcard,
  assessment-item, exam-blueprint, and study-brief content; extra/unknown fields
  and invalid discriminated unions fail closed.
- [x] Artifact provenance is a strict origin union: generated binds verified
  run/prompt/model/validator/pins/output/dependencies and binds a closed profile
  receipt exactly for flashcards; human-authored
  binds HUMAN plus an exact interaction and forbids generated-only fields.
- [x] Optional media is a closed trusted BlobId/digest/source-index/verifier
  receipt/alt-text value; filenames, embedded markup, and unverified media fail.
- [x] Profile catalog is immutable, closed, provider-free, and cannot
  self-register; general hybrid is the explicit default and morphology-first is
  never inferred from course title or model output.
- [x] A typed selection receipt makes default/explicit/trusted-metadata choice
  auditable; morphology requires a trusted evidence reference and model output
  cannot author or override the receipt.
- [x] Agent-facing descriptors state selection rules, budget ceilings,
  framework/atomic roles, grounding, and exporter-neutral constraints.
- [x] Assessment-item and study-brief v1 schemas implement the minimal closed
  ADR-0008 fields and reject attempts, grades, mastery, scheduling, learner
  models, Anki fields, and HTML/template metadata.

## Verification

- Domain/codec/catalog unit contracts, portability firewall, identity golden
  fixtures, architecture imports, Ruff, strict mypy, and full offline gates.

## Grilling Evidence

- Adaptive-tutor global grilling, ADR-0008, repository evidence review, and
  independent architecture report on 2026-07-15.
