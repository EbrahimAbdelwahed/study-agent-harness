# Worker Brief: TUT-04C shared scope and media foundation

## Goal

Provide the private, provider-neutral preparation seam required by both
flashcard profiles: a truthful whole-scope structural index plus bounded active
evidence, and a trusted resolver for optional morphology media handles.

## Allowed Files

- `src/study_agent/flashcards/__init__.py`
- `src/study_agent/flashcards/scope.py`
- `src/study_agent/ports/flashcard.py`
- `src/study_agent/tools/flashcard_scope_bridge.py`

## Forbidden Files

- Public StudyTool manifests/registry, existing ports/tools, capabilities,
  candidates, prompts, skills, playbooks, adapters, events/state, tests,
  docs/specs, dependencies, configuration, CLI/export, and `sbobby-web`.

## Required Contracts

- `FlashcardScopeIndexEntry` is immutable and exact: deterministic opaque
  `topic_key`, trimmed heading and locator, contiguous zero-based
  `relative_position`, positive `character_count`, and unique ordered active
  evidence handles. Index entries are metadata, never generated summaries.
- `PreparedFlashcardScope` contains 1..256 canonically ordered unique entries,
  one strict `EvidenceEnvelope` with at most 24 active items, and a lowercase
  SHA-256 fingerprint. Positions must equal `range(len(entries))` and tuple
  order is canonical. The fingerprint is exactly
  `SHA256(b"prepared-flashcard-scope@1\\0" + canonical_json({"index": ..., "evidence": ...}))`;
  it excludes the fingerprint field itself and commits only to the returned
  scope, not to an unprovable claim of source completeness. Every
  linked evidence handle exists in the envelope; an entry may have none.
- Exact JSON/byte codecs reject unknown fields, reorderings, forged
  fingerprints, duplicate topics/positions/handles, unbounded values, or
  non-canonical bytes. `from_bytes()` must decode JSON, apply `freeze_json`
  before reconstructing tuple-exact values and `EvidenceEnvelope`, then require
  byte-for-byte equality with the canonical encoding.
- `FlashcardScopePreparationPort.prepare(context, query, scope)` returns the
  trusted bundle for the exact course/session request. It owns whole-scope
  enumeration and bounded evidence selection; `source.search` top-k is not a
  substitute. Its exact signature is
  `prepare(context: ExecutionContext, query: str, scope: str | None) -> PreparedFlashcardScope`.
  Whole-scope completeness is the semantic obligation of the trusted
  implementation/adaptor; the value codec and unit tests must not pretend to
  prove it. A durable source-catalog receipt is intentionally deferred.
- `VerifiedMediaEvidence` is a strict pre-batch trusted record: opaque handle,
  active evidence handle, `BlobId`, matching lowercase SHA-256, exact source
  `Citation`, portable verifier id/version/fingerprint, and alt text. It must not
  contain a `source_commitment_index`, because commitment ordering does not exist
  until TUT-04E materializes a canonical proposal batch.
- `VerifiedMediaEvidencePort.resolve(handle)` returns that existing record or
  fails. Handles are opaque and no filename/blob/verifier receipt is
  model-authored. TUT-04E alone converts it to `VerifiedMediaRef` after resolving
  the citation to the final source-commitment index.
- `BoundFlashcardScopeExecutor` is a private playbook `ToolExecutor` named
  `source.prepare_flashcard_scope@1`. It closes over trusted
  `ExecutionContext`, query, nullable scope, and port. Invocation arguments are
  exactly `{"query": <str>, "scope": <str-or-null>}` and must match those
  trusted values; context and principal identifiers are never accepted or
  serialized as invocation arguments.
  It returns only `PreparedFlashcardScope.to_json()`.
- Do not add an eighth public StudyTool or package-specific state owner. Actual
  filesystem/database preparation adapters and runtime registration are later
  composition work.
- Keep value contracts in `flashcards/scope.py` importing only inward domain and
  grounding values; keep protocols in `ports/flashcard.py`; keep the private
  executor in `tools/flashcard_scope_bridge.py`. `flashcards` must not import
  ports/tools/capabilities, and ports must not import tools/playbooks/capabilities.

## Verification

- `.venv/bin/ruff check src`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- Existing tool-count and architecture tests.
- `git diff --check`

## Report

Report exact public names, bounds, codec fingerprint domain, and commands.
Do not edit tests, commit, or delegate.
