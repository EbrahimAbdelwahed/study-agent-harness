# PF-05 — Sources and citations

## Outcome

Hosts can ingest immutable source revisions and resolve source-bound citations
from canonical bytes. Source identity, revision identity, normalized substrate,
blob identity, citation identity, and derived projections stay separate so
replay and grounding never treat a model summary or index row as primary
evidence.

## Non-goals

- No live web connector, candidate web evidence broker, cookies, credentials,
  arbitrary URL fetch, or automatic source admission.
- No Cardine educational authority, currency, integrity, syllabus, or
  curriculum alignment policy.
- No new parser, OCR, PDF, or embedding dependency; existing adapters remain
  optional and host-composed.

## Exact contracts

- `SourceId` identifies a logical learner material; `RevisionId` identifies one
  immutable revision. A revision stores source ID, content blob hash/length,
  media type, creation instant, normalization version, normalized substrate
  reference, and opaque source metadata. A new revision never mutates an old
  one.
- Blob identity is lowercase SHA-256 over canonical bytes. Raw bytes and
  normalized substrate have independent blob and substrate IDs. Derived KB
  units, lexical indexes, and projections carry revision lineage but cannot
  replace the source revision.
- Public evidence names are explicit: `SourceEvidence`, `LearningEvidence`,
  `RetentionObservation`, and `CandidateWebEvidence`. The bare name
  `Evidence` is not a public contract.
- `TextCitationV2` binds source ID, revision ID, unit ID, substrate ID, exact
  non-empty code-point span, quoted SHA-256, optional locator, and optional page
  hint. `FigureCitationV1` binds figure bytes and optional anchor. Locators and
  hints are display links, not identity.
- Citation minting and resolution read canonical bytes supplied by the source
  port. The verifier checks source/revision/unit agreement, substrate hash,
  span bounds, and quoted hash. Missing, corrupt, superseded, out-of-unit,
  unsupported, and mismatched citations fail closed with typed citation
  failures mapped through PF-02.
- A `ResolvedCitation` identifies current/superseded status and any successor
  revision. Historical citations remain readable; a supersession projection
  never rewrites the original citation.
- `DerivedRef` and model-generated text always point to a canonical citation
  and are explicitly non-canonical. Derived synthesis retains claim lineage and
  cannot become a primary source.
- Source paths and external file ownership remain with the host. Harness
  accepts bytes or a host-owned source input port and never scans arbitrary
  directories.

## Probable files

- `src/study_agent/api/sources.py` — source, revision, blob, and citation exports.
- `src/study_agent/domain/source.py` and `src/study_agent/domain/citation_v2.py`
  — stable value contracts and codecs.
- `src/study_agent/knowledge/citation.py`, `src/study_agent/knowledge/projections.py`,
  and `src/study_agent/ports/source_input.py` — verification and port wiring.
- `src/study_agent/ingestion/identity.py`, `src/study_agent/ingestion/service.py`,
  and `src/study_agent/adapters/filesystem/source_input.py` — immutable source
  adapter boundary.
- `tests/contract/source_content/test_source_content_contract.py`,
  `tests/contract/sources/test_source_revision_contract.py`,
  `tests/contract/sources/test_citation_contract.py`.
- `tests/integration/test_source_content_resolution.py`,
  `tests/integration/test_source_projection_replay.py`, and
  `tests/unit/knowledge/test_citation_v2.py`.

## Dependencies

PF-03 provides event lineage and PF-04 provides blob/source storage ports.
PF-07 consumes `SourceEvidence` and citation references. Future web evidence
uses these contracts but is not part of this slice.

## Removal conditions

Remove any legacy citation alias only after its decoder and historical fixtures
are covered by a deterministic upcaster. Do not retain a second verifier or a
snippet-only fallback after PF-05 acceptance.

## Review surface

Review identity separation, hash binding, source path ownership, supersession
handling, and the guarantee that derived text cannot verify as evidence.
Inspect a replay with old and new revisions and a citation against stale,
corrupt, and out-of-unit bytes.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/source_content tests/contract/sources tests/unit/knowledge/test_citation_v2.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_source_content_resolution.py tests/integration/test_source_projection_replay.py tests/integration/test_text_ingestion.py
uv run --python 3.13 --extra dev ruff check src/study_agent/domain/source.py src/study_agent/domain/citation_v2.py src/study_agent/knowledge src/study_agent/ingestion src/study_agent/api/sources.py tests/contract/sources
git diff --check
```

Fixtures must cover equal-byte revision identity, changed bytes, normalized
substrate separation, current and superseded citations, all citation failure
kinds, derived-reference rejection, and deterministic export/replay.

## Risks

- A snippet or retrieval index can be mistaken for canonical bytes. Keep the
  verifier's bytes and unit binding explicit and require hash agreement.
- Revision IDs can be conflated with logical source IDs. Enforce both fields in
  every source, citation, and evidence value.
- Host paths and external URLs can leak into identity or trust. Store opaque
  host metadata and keep admission/policy outside this portable seam.

## Definition of done

- Source/revision/blob/substrate/citation values are frozen, versioned, and
  importable from `study_agent.api.sources`.
- Canonical citation verification passes all failure and supersession fixtures.
- Derived references are visibly non-canonical and retain source lineage.
- Existing KB v0.2 replay/citation fixtures remain green without new required
  dependencies.
- Focused contract, integration, lint, and diff checks pass.
