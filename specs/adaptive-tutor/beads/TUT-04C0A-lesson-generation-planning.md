# Task Bead: TUT-04C0A lesson generation planning

Status: Done
Priority: P0
Type: expand
Depends On: TUT-04C0

## Worker Profile

Reuse `grounded-study-artifact-worker`; use `test-engineer` for independent
planner, codec, and boundary fixtures.

## Context

ADR-0010 replaces an undefined whole-scope card quota with the proven
lesson-index plus bounded-topic-bundle method. This bead copies the structural
method from `scripts/repair_embrio04_10_quality.py`, not its course-specific
budgets, regexes, or Anki output.

## Outcome

The harness can deterministically turn one trusted ordered lesson scope into a
fingerprinted global topic index and ordered, non-overlapping active bundles
before any model call.

## Acceptance Criteria

- [ ] Strict provider-neutral contracts represent one host-declared lesson unit,
  ordered source revisions/spans, global topic index, bundle plan, planning
  policy receipt, and plan fingerprint without adding canonical learner state.
- [ ] A new strict `PreparedPlannedFlashcardScope` contract wraps the existing
  byte-compatible `PreparedFlashcardScope` with plan fingerprint, bundle
  identity/kind, canonically ordered active topic keys, and trusted eligibility/
  priority. C0A defines the wrapper; B2 constructs it after resolving slots.
  `source.prepare_flashcard_scope@1` and its bytes remain unchanged.
- [ ] Topic entries retain stable topic key, title, heading level, parent,
  canonical source span/locator, direct and subtree visible sizes, relative
  order, and closed `eligible|context_only|excluded` plus
  `core|supporting|none`
  planning classifications.
- [ ] Classification is supplied by a versioned trusted planning policy or a
  conservative generic structural policy. The OSS core contains no
  Casasco/embryology regex, subject-specific quota, or model-authored authority.
- [ ] Bundle construction preserves topic and paragraph order, prefers complete
  heading/subtree boundaries, targets approximately 5,000 visible source
  characters as a versioned soft limit, contains at most 24 planned evidence
  slots, and splits an oversized topic only at whole canonical paragraph
  boundaries. One slot may commit to one contiguous combined paragraph span.
- [ ] Every content paragraph/span appears in at most one active bundle; gaps,
  overlap, reordered spans, duplicated topic ownership, and forged plan
  fingerprints fail closed.
- [ ] The compact global index is separate from bundle evidence. Index headings
  provide scale/navigation but cannot support factual claims; each bundle names
  exact canonical source/paragraph spans. C0B resolves those spans into the
  bounded active evidence allowlist immediately before worker execution.
- [ ] The global topic index contains at most 256 entries. A larger lesson fails
  explicitly with `lesson_index_limit_exceeded`; it is never truncated. C0B
  resolves every planned slot into one bounded evidence item so the final
  `EvidenceEnvelope` also remains within its existing 24-item contract.
- [ ] Planning records eligibility and priority, not a desired card count. No
  lesson minimum, 16–22 target, fixed per-topic quota, or proportional
  long-section expansion enters the default policy.
- [ ] Empty/context-only lessons produce an explicit no-work plan. Oversized
  single paragraphs are retained intact with a truthful soft-limit-exceeded
  marker rather than truncated or overlapped.
- [ ] Exact codecs, deterministic fingerprints, old source replay, architecture
  boundaries, and the seven public StudyTools remain unchanged.

## Likely Files / Packages

- `src/study_agent/flashcards/planning.py`
- `src/study_agent/ports/flashcard.py`
- `src/study_agent/flashcards/__init__.py`
- focused unit/architecture tests under `tests/unit/flashcards/` and
  `tests/architecture/`

## Out of Scope

- Model calls, worker scheduling, capability dispatch, prompt behavior, artifact
  commit, UI, provider adapters, PDF/OCR/audio, Anki export, and `sbobby-web`.

## Verification

- Historical-shape fixture: one lesson with nested headings and paragraph spans
  yields the expected global index and contiguous bundles.
- Empty, scaffolding, exact-boundary, oversized paragraph, overlap, reordering,
  multi-source, forged receipt/fingerprint, and canonical-byte fixtures.
- Ruff, strict mypy, architecture/tool parity, and full offline gates.

## Grilling Evidence

Approved ADR-0010 and direct repository evidence from
`dev/notes/2026-06-27-2230--anki--hierarchical-card-prompt-design--note.md`;
course-specific constants and historical lack of durable continuation were
explicitly rejected.
