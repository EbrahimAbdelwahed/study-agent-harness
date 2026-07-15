# Worker Brief: TUT-04A production

## Goal

Implement the closed provider-neutral study-artifact, provenance, identity, and
pedagogical-profile contracts approved by ADR-0008.

## Worker Profile

Reuse `grounded-study-artifact` from
`specs/adaptive-tutor/worker-profiles/grounded-study-artifact.md`.

## Allowed Files

- `src/study_agent/domain/identifiers.py`
- `src/study_agent/domain/artifact.py`
- `src/study_agent/domain/__init__.py`
- `src/study_agent/artifacts/__init__.py`
- `src/study_agent/artifacts/content.py`
- `src/study_agent/artifacts/identity.py`
- `src/study_agent/pedagogy/__init__.py`
- `src/study_agent/pedagogy/profiles.py`

## Forbidden Files

- Events, reducers, services, views, ports, capability/gateway/playbook/prompt/
  skill code, export/CLI/composition roots, tests, docs/specs, adapters, tools,
  state, sessions, `sbobby-web`, dependencies, and repository configuration.

## Required Context

- ADR-0008 and TUT-04A.
- `domain/provenance.py`, `_validation.py`, `identifiers.py`, capability manifest
  and portability patterns.
- The two flashcard methods are already normalized into ADR-0008; do not import
  personal skill files or their Anki/Casasaco examples into production.

## Required Contracts

- Add distinct typed `ArtifactId`, `ArtifactRevisionId`, and `ArtifactBatchId`;
  deterministic functions derive batch from trusted course/session/retry
  identity, artifact from batch+ordinal, and revision from canonical
  artifact/kind/content/provenance/prior-revision bytes. Candidate/model keys are
  never identity inputs.
- Define closed artifact kind, revision status, decision, retrieval-form, and
  profile-specific role/family/function vocabularies required by ADR-0008.
- Define immutable `PedagogicalProfileRef`, descriptor, selection mode/basis,
  selection receipt, and catalog. Default is exactly hybrid. Morphology requires
  explicit-request or trusted-metadata basis linked to a typed learner
  interaction or source revision reference. MODEL cannot be selector authority.
- Descriptors expose structured host guidance: selection rule, recommended
  ceilings, hard ceiling/ratios, ordered roles, grounding and exporter-neutral
  invariants. They contain no provider/model/runtime/Anki/deck/tag preference.
- Define one immutable content envelope and exact codecs for:
  - flashcard: profile-discriminated direct-recall/contextual-gap content,
    structured answer blocks, role/function, rationale, parent linkage, and
    optional closed `VerifiedMediaRef(BlobId, sha256, source commitment index,
    verifier id/version/fingerprint, alt text)` values;
  - assessment item: format, prompt, options, expected response, evaluation
    criteria; no attempt/grade/mastery/schedule;
  - exam blueprint: sample size, observed topic/format evidence, limitations;
  - study brief: title, objective, bounded sections with heading/summary/key
    points, and limitations; no learner model or schedule.
- Exact decoders reject unknown/extra fields, invalid unions, Anki-shaped
  `basic`/`cloze`, deck/tag/template/raw-HTML/media-name fields, provider
  selectors, credentials, decisions, status, canonical IDs inside content, and
  empty/duplicate/unbounded collections.
- Define a strict provenance union with an origin discriminator:
  - `generated` composes existing prompt/model/retrieval/validator/source/version
    leaves plus profile selection, ordered read dependencies, output fingerprint,
    and run identity; model is optional only when the verified procedure truly
    made no model call, while prompt/validator/run proof remains required;
  - `human_authored` requires `PrincipalKind.HUMAN`, an `InteractionId`, source
    commitments/read dependencies and optional prior revision, and structurally
    forbids prompt/model/validator/pins/run/output/profile-selection fields.
  Observed technical provider/model receipts are retained; selection policy and
  secrets are not.

## Acceptance Criteria

- All public values freeze nested JSON and serialize deterministically.
- Verified media rejects basename/Anki filename semantics, missing source
  linkage, malformed digest/receipt, unverified flags, and embedded HTML.
- Profile/content/provenance codecs round-trip byte-identically.
- Imports remain domain inward; no capability, adapter, UI, or provider SDK
  dependency enters domain/artifacts/pedagogy.
- No event/state owner or runtime registration is introduced in this bead.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing domain/portability/capability contract tests.
- `git diff --check`

## Report

Report exact public names, schema choices, commands/results, and any ADR conflict.
Do not commit or delegate.
