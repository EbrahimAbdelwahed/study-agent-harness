# Worker Brief: TUT-04D grounded exam-sample analysis tests

## Goal

Independently pin the public contract, grounding, injection/prediction failure,
and one-worker isolation semantics of `analyze_exam_sample@1`.

## Allowed Files

- `tests/unit/exams/test_exam_scope_contracts.py`
- `tests/unit/exams/test_exam_analysis.py`
- `tests/unit/exams/test_exam_worker.py`
- `tests/contract/capabilities/test_exam_sample_capability.py`
- `tests/integration/test_grounded_exam_sample_analysis.py`
- `tests/architecture/test_exam_analysis_boundaries.py`

## Forbidden Files

- Production, existing tests/fixtures, flashcard B2/C1/C2 files, artifact commit,
  specs/docs, dependencies, provider SDKs, `sbobby-web`, and network tests.

## Required Coverage

- Exact `PreparedExamSampleScope` round trip, canonical-byte rejection,
  fingerprints, ordered unique sample/revision/handle bindings, literal
  `exam_sample` role, current/course ownership, complete-sample and 16-sample/
  64-evidence/8-per-sample/64-KiB bounds. Prove failures do not truncate.
- For every selected revision prove exact ordered span coverage
  `[0, normalized_character_length)` and reject gaps, overlap, reorder, missing
  head/tail, duplicate chunks, or partial retrieval. Prove the separate prompt
  projection removes canonical course/source/revision/chunk ids while retaining
  an exact resolvable scope fingerprint and opaque handle mapping.
- Capability manifest/schema snapshot: exact inputs/output, `course:read`, no
  suspension, empty writes, no forbidden learner/prediction/provider/authority/
  artifact fields, stable existing capability and seven-tool fingerprints.
- Task factory goldens pin `build(request, opaque_request_key)` determinism and
  changed request/key conflicts. Facade start/detail always rebuild the same task;
  neither accepts task id nor reads/discovers worker-store state by task/run id.
- Prompt composition keeps source text as untrusted evidence. Fixtures cover
  role delimiters, instruction override, prompt/credential exfiltration, and
  Unicode/case variants; readiness terminates before recording any model call.
- Scripted model fixtures cover sparse samples, conflicting evidence, only
  topics, only formats, both empty, unknown/unresolved handles, duplicate
  normalized values, missing citations, extra fields, malformed JSON, and
  prediction/likelihood/future-exam language.
  Topics-only and formats-only both terminate as insufficient.
- Assert limitations are byte-stable and validator-derived in exact order;
  model output cannot add, remove, or rewrite them. `sample_size` counts selected
  revisions, while evidence coverage counts distinct cited handles.
- Recording ports prove exactly one B1 `EXAM_ANALYSIS` task, one child
  capability run/model effect, exact pins/validator sequence, revision refs only
  in task evidence references/capability input, and no tutor history, unrelated
  materials, raw principal/session/credential/provider data, sibling drafts, or
  canonical write authority in task bytes or prompt messages.
- Retry after terminal completion reuses the same receipt; cancellation,
  failure, stale binding, mismatched authority, and unauthorized detail follow
  B1 semantics without a second effect. Compact view contains only counts/codes;
  typed detail contains verified proposal/evidence mapping and no raw reasoning.
- Recording proof readers assert the injected type is
  `ExamVerifiedChildProofReader` with the B1A owner load shape. D derives child
  context with the public helper and loads by exact task, child run, B1 receipt,
  and child context—never parent; changed-task/context/authority fail. It derives
  mapping and coverage from sanitized verified prepared tool
  output and read dependencies, and cannot read tampered/wrong-authority or
  competing-receipt proof.
- Preparation tool result is exact `{prepared_scope, prompt_projection}`. Record
  prompt composition to prove ModelStep receives only the projection path.
  Detail rejects wrong tool id/version/step/output key/fingerprint, extra/missing
  members, noncanonical scope/projection, mismatched scope commitment, and
  changed handle mapping.
- Integration proves trusted upload revisions -> isolated analysis -> verified
  proposal detail with no attempt, grade, mastery, schedule, decision, proposal
  event, or accepted artifact written.

## Verification

- `PYTHONPATH=. .venv/bin/pytest -q tests/unit/exams tests/contract/capabilities/test_exam_sample_capability.py tests/integration/test_grounded_exam_sample_analysis.py tests/architecture/test_exam_analysis_boundaries.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/contract/tools/test_public_tool_contract.py tests/architecture/test_artifact_contract_boundaries.py`
- `.venv/bin/ruff check <new production and test files>`
- `.venv/bin/mypy --strict <new production files>`
- `PYTHONPATH=. .venv/bin/pytest -q`
- `git diff --check`
