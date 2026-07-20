# Worker Brief: TUT-04C1 hybrid profile tests

## Goal

Independently pin the hybrid prompt/skill/playbook, the concrete B2 profile
adapter, the B1A proof-preserving profiled execution path, and fail-closed
integrity without asserting subjective semantic quality.

## Allowed Files

- `tests/unit/prompts/test_hybrid_flashcards_prompt.py`
- `tests/unit/skills/test_hybrid_flashcard_skill.py`
- `tests/unit/playbooks/test_hybrid_flashcards_flow.py`
- `tests/unit/capabilities/test_hybrid_flashcards.py`

## Forbidden Files

- Production, existing tests, fixtures outside these files, docs/specs,
  dependencies, configuration, and `sbobby-web`.

## Acceptance Criteria

- Prompt tests pin compact-global-index/local-active-evidence separation,
  section-before-earned-detail order, frameworks versus fragile/non-recoverable
  facts, ceilings-not-quotas, valid zero-card omissions, untrusted data and shape
  examples, and prohibitions on 16–22/whole-lesson targets, paragraph coverage,
  Anki fields, providers, canonical state, and prompt injection.
- Skill/playbook tests pin exact private identities, planned-scope tool, public
  schemas, private draft schema, reserved non-effect profile receipt, one
  request-bound tool, one gated dialogue, exactly one model effect, exact
  bindings, ordered validators, fallback validator, empty state writes, and
  final public `candidate_batch`. Non-null B2 scope follows the no-dialogue
  default; null direct-use scope suspends.
- Adapter tests construct the final C0A/B2 wrapper and prove that
  `expectation` and `build` satisfy every B2 task comparison. Changed request,
  wrapper, plan/profile/prompt/tool/model/state/validator pin, authority,
  continuation summary, index reference, evidence order, or output schema fails
  closed. No mutable registry or hidden lookup is exercised.
- End-to-end recording tests prove one B2 page invokes one complete B1 child run
  and exactly one playbook ModelStep. The B1 task/input/receipt fingerprint uses
  only the five public fields; gateway execution adds the canonical trusted
  hybrid profile receipt; no effect binding can read it. B1A still stores and
  reloads its sanitized proof. Retry/detail use identical commitments. Tutor
  history, sibling output, inactive source text, credentials, principal data,
  provider selection, and raw wrapper bytes never enter the ModelRequest.
- Integrity fixtures cover direct section/detail, sparse section-only,
  multi-topic framework, and zero-card grounded omission success. Reject
  missing/reordered/duplicate/unknown topic plans; cards owned by omission;
  inactive claims; missing/extra detail bases; invalid role/parent order;
  morphology/media/contextual-gap fields; ceiling excess; unknown, unlinked,
  empty, drifted, or reordered evidence; duplicate/containment-equivalent
  content; malformed fallback envelope; extra/injection-shaped/Anki fields; and
  stale wrapper/plan/bundle fingerprints.
- Tests distinguish deterministic validation from prompt/eval judgments: they
  do not claim to prove factual importance, true fragility/non-recoverability,
  semantic equivalence, ideal line counts, or ideal visible-character density.

## Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/prompts/test_hybrid_flashcards_prompt.py \
  tests/unit/skills/test_hybrid_flashcard_skill.py \
  tests/unit/playbooks/test_hybrid_flashcards_flow.py \
  tests/unit/capabilities/test_hybrid_flashcards.py \
  tests/unit/capabilities/test_worker_adapter.py \
  tests/unit/workers/test_worker_proof.py \
  tests/unit/flashcards/test_lesson_worker_service.py \
  tests/unit/tools/test_planned_flashcard_scope_bridge.py \
  tests/architecture/test_capability_bindings.py \
  tests/architecture/test_lesson_worker_boundaries.py \
  tests/contract/tools/test_public_tool_contract.py
.venv/bin/ruff check \
  tests/unit/prompts/test_hybrid_flashcards_prompt.py \
  tests/unit/skills/test_hybrid_flashcard_skill.py \
  tests/unit/playbooks/test_hybrid_flashcards_flow.py \
  tests/unit/capabilities/test_hybrid_flashcards.py
.venv/bin/mypy --strict \
  tests/unit/prompts/test_hybrid_flashcards_prompt.py \
  tests/unit/skills/test_hybrid_flashcard_skill.py \
  tests/unit/playbooks/test_hybrid_flashcards_flow.py \
  tests/unit/capabilities/test_hybrid_flashcards.py
git diff --check
```

## Report

Report production mismatches, exact passing/failing commands, and whether each
assertion covers a validator-enforced invariant or a prompt/eval policy. Do not
edit production, commit, or delegate.
