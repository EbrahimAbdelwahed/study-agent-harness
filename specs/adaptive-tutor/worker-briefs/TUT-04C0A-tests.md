# Worker Brief: TUT-04C0A lesson planning tests

## Goal

Independently pin lesson indexing, intelligent paragraph/topic bundling, strict
codecs, and provider/state boundaries without asserting semantic importance that
the deterministic planner cannot know.

## Allowed Files

- `tests/unit/flashcards/test_lesson_planning.py`
- `tests/architecture/test_flashcard_planning_boundaries.py`

## Acceptance Criteria

- A nested-heading lesson fixture produces the exact global index, parent order,
  classifications, and contiguous non-overlapping bundles expected from the
  historical lesson/bundle method.
- Exact 5,000-character and 24-slot boundaries pass; adjacent topics combine
  when within both bounds; a topic crosses bundles only at complete paragraph
  boundaries; an oversized paragraph remains whole and is marked truthfully.
- Index sizes 1 and 256 pass; 257 fails with
  `lesson_index_limit_exceeded` and no partial/truncated plan.
- Empty/context-only, one-topic, multi-source, nested subtree, policy
  override, and explicit skip fixtures pass.
- Missing/reordered parents, invalid nesting, overlapping/duplicated/gapped
  active spans, non-contiguous positions, unknown source/span identities,
  forged policy/plan fingerprints, extra fields, invalid list shapes, and
  non-canonical bytes fail closed.
- Tests pin that the global index is navigation metadata and bundle source spans
  are a distinct allowlist later resolved one-slot-to-one-item by C0B, never
  exceeding 24 evidence items. They do not claim
  headings alone prove source completeness or pedagogical importance.
- Wrapper codec/fingerprint fixtures prove exact plan/bundle/topic/
  classification binding and byte-for-byte non-regression of the existing
  `PreparedFlashcardScope` plus `source.prepare_flashcard_scope@1` contract.
- Negative architecture fixtures forbid imports from prompts/skills/playbooks/
  capabilities/adapters/state and preserve exactly seven public StudyTools.
- No test expects a lesson card count, local quota, 16..22 range, or mandatory
  output per content topic.

## Verification

- Focused pytest, Ruff, strict mypy, architecture/tool parity, and
  `git diff --check`.

## Report

Report production mismatches only; do not edit production, commit, or delegate.
