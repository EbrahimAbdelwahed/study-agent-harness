# Worker Brief: TUT-04C0A lesson generation planning

## Goal

Implement the deterministic, provider-neutral planner that converts one trusted
ordered lesson scope into a compact global topic index and ordered,
non-overlapping active bundles according to ADR-0010.

## Allowed Files

- `src/study_agent/flashcards/planning.py`
- `src/study_agent/ports/flashcard_planning.py`

## Forbidden Files

- Existing files and exports, prompts, skills, playbooks, capabilities, model
  adapters, artifact/event/state owners, CLI, configuration, dependencies,
  tests, specs/docs, C1/C2 partial implementation, and `sbobby-web`.

## Required Contracts

- Define strict immutable values for a host-declared lesson unit, canonical
  ordered paragraph/source spans, lesson topics, planning classifications,
  planned bundles, planning-policy receipt, and the complete lesson plan.
- Define strict `PreparedPlannedFlashcardScope` as the unchanged completed
  `PreparedFlashcardScope` plus exact plan fingerprint, bundle id/kind,
  canonically ordered active topic keys, and trusted eligibility/priority for
  those keys. Its codec/fingerprint is new and versioned; do not edit, alias, or
  silently widen `PreparedFlashcardScope` or `source.prepare_flashcard_scope@1`.
- Topic index fields are exact: deterministic opaque topic key; trimmed title;
  heading level; nullable earlier parent key; contiguous relative position;
  canonical source locator/span identity; positive direct/subtree visible sizes;
  `eligible|context_only|excluded`; `core|supporting|none`. These trusted
  planner terms are intentionally distinct from model-authored dispositions.
- Define a provider-neutral trusted `FlashcardPlanningPolicy` protocol. It may
  classify/override structural topics and must return a portable id, version,
  fingerprint, and exact classification result. Model-authored classification,
  course-specific regexes, and inferred provider identity are forbidden.
- Provide a conservative deterministic default structural policy: containers or
  empty headings may be `context_only`; source-bearing leaf/subtree topics
  remain `eligible` unless trusted input says otherwise. It must not recognize Casasco,
  subject names, exam importance, or assign card quotas.
- Planner input is already canonical/ordered. Validate parent-before-child,
  heading nesting, source-span ordering, paragraph ownership, and non-overlap.
  Do not read files or infer lesson membership inside the value layer.
- The global index is bounded to 256 entries. Reject 257+ explicitly with
  `lesson_index_limit_exceeded`; never truncate, silently omit, or renumber.
- Bundle selected eligible topics in canonical order. Prefer whole topic/subtree
  boundaries. Target a versioned soft maximum of 5,000 visible active-source
  characters and enforce at most 24 planned evidence slots per bundle. If one
  topic exceeds either bound, group complete paragraphs in order; one oversized
  paragraph remains intact in one marked bundle. A slot may commit to one
  contiguous combined paragraph/source span.
- Every active paragraph/span belongs to exactly one bundle. Bundles are
  contiguous, pairwise disjoint, canonically ordered, and name exact topic keys
  plus canonical source/paragraph spans. Evidence handles do not exist at this
  planning boundary; C0B resolves each planned slot into one bounded evidence
  item immediately before execution, preserving the existing <=24-item
  `EvidenceEnvelope`. Context-only topics may inform the global index but own no
  active factual evidence unless a trusted policy marks them eligible.
- Plan fingerprint is domain-separated and commits to unit, source identities,
  exact index, bundles, configuration, and policy receipt without self-reference.
  Exact JSON/byte codecs freeze decoded arrays and reject non-canonical bytes,
  unknown fields, forged fingerprints/receipts, gaps, overlap, duplication, and
  reordered spans.
- A lesson with no selected content yields a valid explicit no-work plan. There
  is no lesson/card minimum, 16..22 target, local card count, Anki field, model
  field, state write, or StudyTool.

## Historical Shape to Preserve

Reuse the structural behavior evidenced by
`scripts/repair_embrio04_10_quality.py`: whole lesson index first, ordered
contiguous topic bundles around 5,000 source characters, global index separated
from active source. Do not copy its hard-coded lesson budgets, 62% allocation,
Casasco regexes, mandatory topic output, HTML/tags, or overlapping transcript
segments.

## Verification

- Ruff and strict mypy for new modules.
- Existing source/flashcard architecture and seven-tool tests.
- `git diff --check`.

## Report

Report exact public names, canonical bounds/fingerprint domain, default-policy
limits, and verification commands. Do not edit tests, commit, or delegate.
