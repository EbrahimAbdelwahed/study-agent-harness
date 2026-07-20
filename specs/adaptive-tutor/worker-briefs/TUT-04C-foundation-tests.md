# Worker Brief: TUT-04C shared scope and media foundation tests

## Goal

Pin whole-scope preparation truthfulness, exact codecs, the request-bound
private executor, media resolution protocol, and unchanged public tool surface.

## Allowed Files

- `tests/unit/flashcards/test_scope_contracts.py`
- `tests/unit/tools/test_flashcard_scope_bridge.py`
- `tests/architecture/test_flashcard_scope_boundaries.py`

## Acceptance Criteria

- Empty/257/reordered/duplicate/forged index fixtures fail; 1 and 256 pass.
- Missing/duplicate/out-of-envelope active handles, 25 evidence items, malformed
  metadata, extra fields, forged fingerprints, invalid array shapes/types, and
  non-canonical bytes fail closed. Valid JSON arrays decoded as lists are frozen
  into tuple-exact values and pass canonical byte decoding.
- Exact round trips preserve index/evidence identity and scope fingerprint.
- Fingerprint fixtures pin the domain-separated formula over exact canonical
  `{index,evidence}` bytes, exclude the fingerprint itself, and require
  contiguous positions equal to `range(len(entries))`.
- Bound executor accepts only exact public `query` and nullable `scope`
  arguments, uses the trusted context captured at construction, and returns the
  exact single port result; mismatch or extra context/principal arguments fail
  before port invocation. Tests assert request binding and one port invocation,
  not arbitrary source completeness.
- Media protocol binds handle/evidence/blob/digest/citation/verifier/alt text,
  rejects any premature source-commitment index, and exposes no provider, path,
  Anki, model, or state-write contract.
- Public StudyTools remain exactly seven; no capability/event/state owner or
  provider adapter enters the foundation.
- Architecture tests forbid `flashcards -> ports/tools/capabilities` and
  `ports -> tools/playbooks/capabilities`; the bridge alone imports ports plus
  playbook executor contracts.

## Verification

- New focused tests, Ruff, strict mypy, relevant architecture tests, and
  `git diff --check`.

## Report

Report production mismatches only; do not edit production, commit, or delegate.
