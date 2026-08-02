# Plan: selective public agent tool surface

Date: 2026-08-02 11:35 CEST
Area: tools

## Goal

Expose the active Harness's canonical course, ingestion, session, artifact,
assessment, retrieval, context, and evidence operations to external agents
without merging the divergent `codex/public-tool-surface-main` history or
duplicating owner behavior.

## Audit and Grilling Evidence

- Read-only branch audit: `f717e39` is the only feature commit; `1c6ce65`
  changes two plan lines. The feature cannot be cherry-picked because it
  imports the removed recall lane and its ancestor carries unrelated KB,
  browser, PDF-workaround, capability-gap, CLI/release, and documentation work.
- Read-only owner audit: the active checkout has canonical owners for course
  creation, text ingestion, session lifecycle and learner turns, artifact and
  assessment projections, plus the existing seven retrieval/context/evidence
  tools. Artifact and assessment writes are not safely composable without
  verified generated-owner/accepted-artifact preconditions.
- Active KB audit: KB-13 `EvidenceService` exists but is not composed by
  `LocalRepository`; changing retrieval ownership is a separate product and
  composition decision, so the current canonical `source.search` and
  `citation.resolve` bindings remain unchanged.
- Baseline verification: 38 focused tool, contract, composition, discovery,
  and architecture tests pass before edits.
- Architecture approval: preserve the exact seven-tool compatibility surface;
  add a separately named runnable inventory, one typed owner bundle, explicit
  course binding, safe ingestion conflict classification, and non-runnable
  recall-unavailable discovery metadata. No ADR or glossary change is needed.

## Scope

- In scope:
  - `course.create` over `CourseService`;
  - `source.ingest_text` over `TextIngestionService`;
  - `session.start|suspend|resume|end` over `SessionService`;
  - `session.record_learner_turn` over `SessionTurnService`;
  - `artifact.proposal_list` over `ArtifactViewPort`;
  - `assessment.get` over `AssessmentViewPort`;
  - the existing retrieval/context/evidence tools, unchanged;
  - `agent-operations@2` discovery with runnable inventory and an explicit
    non-runnable `recall` / `owner_unavailable` entry.
- Out of scope:
  - recall commands, scheduler/FSRS code, or a success-returning fake recall
    tool;
  - artifact proposal generation/acceptance or assessment write flows;
  - KB service recomposition, historical KB code, browser/demo shell, Cardine,
    PDF workarounds, capability-gap work, new CLI command handlers, CI/release
    engineering, README rewrites, dependencies, push/tag/release actions, and
    worktree removal.

## Execution Graph

1. `TOOLS-PUBLIC-01` — adapter and registry tracer bullet (ready).
2. `TOOLS-PUBLIC-02` — behavioral, inventory, authority, idempotency, and error
   tests (depends on 01).
3. `TOOLS-PUBLIC-03` — focused/full verification, independent semantic review,
   approved fixes, dev log, and local commits (depends on 02).

## Task Bead: TOOLS-PUBLIC-01

### Outcome

A repository can compose a course-bound 16-tool registry whose nine new tools
delegate to active canonical owners, while the legacy seven manifests and
private playbook registry remain unchanged.

### Worker Profile

Reuse `typed-tool-harness-worker`; this has the same typed-adapter, closed
schema, authority, and registry shape, with a narrower approved boundary.

### Worker Brief

- May change: `src/study_agent/tools/operations.py`,
  `src/study_agent/tools/builtin.py`, `src/study_agent/tools/registry.py`,
  `src/study_agent/tools/schema.py`, `src/study_agent/tools/__init__.py`,
  `src/study_agent/cli/repository.py`,
  `src/study_agent/cli/registry.py`, the existing tool-discovery helper calls
  in `src/study_agent/cli/commands.py`, `src/study_agent/operator_skill/SKILL.md`,
  and the directly coupled external-agent example.
- Must preserve: exact `public_study_tool_manifests()` seven identities and
  fingerprints; canonical owner behavior; current KB modules and bindings.
- Must implement: one typed `AgentOperationOwners` bundle; complete-or-absent
  extension composition; course mismatch rejection before owner access;
  retryable ingestion/session sequence classification; JSON-only closed
  manifests; a manifest-declared bounded ingestion `content` length; and
  discovery-only recall unavailability.
- Must not: introduce a recall import, owner, command, dependency, or tool;
  expose authority fields in arguments; add artifact/assessment writes; edit
  unrelated CLI handlers, KB, UI, PDF, release, or repository files.

## Task Bead: TOOLS-PUBLIC-02

### Outcome

Tests prove the complete inventory cannot silently shrink, every new runnable
tool reaches its canonical owner, cross-course and missing-capability calls are
effect-free, keyed learner turns are idempotent, convergent operations retry
safely, and recall is advertised only as unavailable metadata.

### Worker Profile

Use the repository `test-engineer` role; no new reusable profile is needed.

### Likely Files

- New focused unit/contract tests under `tests/unit/tools/` and
  `tests/contract/tools/`.
- Narrow inventory/composition updates in
  `tests/contract/cli/test_agent_operation_discovery.py` and
  `tests/integration/test_offline_tool_composition.py`.
- Only directly affected release/example assertions if required by the
  intentional discovery contract bump.

## Acceptance Criteria

- [ ] Legacy seven public study manifests are byte/fingerprint compatible.
- [ ] Expanded runnable inventory contains exactly 16 unique sorted manifests.
- [ ] New adapters call only the current canonical owners.
- [ ] A composed registry rejects mismatched `context.course_id` as
  `unauthorized` before effects.
- [ ] `session.record_learner_turn` requires an idempotency key; course create,
  ingestion, and lifecycle preserve their owners' convergent semantics.
- [ ] Ingestion sequence conflicts and raw event-sequence races classify as
  retryable conflicts; configuration/blob incompatibility fails closed.
- [ ] The ingestion content bound is enforced by the declared input schema,
  with no hidden adapter-only limit.
- [ ] Artifact and assessment exposure is read-only and bounded.
- [ ] Recall is absent from runnable manifests and present as an exact
  `owner_unavailable` discovery record.
- [ ] Discovery remains repository-free, offline, deterministic, and closed as
  `agent-operations@2`.
- [ ] Current KB implementation and retrieval composition are untouched.

## Verification

- `.venv/bin/python -m pytest -q tests/unit/tools tests/contract/tools`
- `.venv/bin/python -m pytest -q tests/contract/cli/test_agent_operation_discovery.py tests/integration/test_offline_tool_composition.py tests/integration/test_tool_harness_parity.py tests/architecture`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy`
- `.venv/bin/python -m pytest -q`
- `git diff --check`
- Independent semantic/regression review before local commits.

## Risks

- Closed discovery consumers require an explicit v2 contract update; historical
  specs remain unchanged.
- The repository worktree already contains unrelated modified/untracked files;
  staging and commits must name only files owned by this plan.
- Full-suite failures may be pre-existing or platform-specific and must be
  distinguished from changed-surface regressions.
