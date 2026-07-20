# Worker Profile: grounded-study-artifact-worker

Generated: 2026-07-16
Source task: `specs/adaptive-tutor/beads/TUT-04-study-artifact-proposals.md`

## Reuse Trigger

Use this worker for a bounded bead that proposes, validates, coordinates, replays,
or exposes source-grounded study artifacts without accepting or publishing them.

## Mandate

Implement one approved study-artifact tracer bullet while preserving canonical
event ownership, source commitments, provider neutrality, and the separation
between operational generation state and accepted learner-visible artifacts.

## Scope

In scope:

- Implement the exact capability, skill/playbook, prompt, worker, coordinator,
  artifact view, or export behavior named by the assigned bead and brief.
- Add focused offline tests for deterministic codecs, grounding, recovery,
  provenance, redaction, and architecture boundaries owned by that bead.
- Reuse existing typed ports and versioned behavior packages.

Out of scope:

- Accepting, publishing, or scheduling artifacts unless the assigned bead
  explicitly owns that transition.
- Product UI, `sbobby-web`, provider SDKs, arbitrary agent loops, long-term model
  memory, learner scoring, or changes to the seven public StudyTools.
- Unrelated refactors, new dependencies, or model-specific adapters.

## Required Context

Read first:

- `specs/adaptive-tutor/README.md`
- the assigned task bead and worker brief
- `docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md`
- `docs/decisions/ADR-0008--study-artifact-proposal-boundary.md`
- `docs/decisions/ADR-0010--lesson-scoped-isolated-generation-workers.md`
- applicable `AGENTS.md` files

Current-doc research:

- not needed; the core uses repository-owned contracts and offline tests. If a
  bead introduces a fast-moving external framework, stop and request a separate
  architecture decision and current primary-source review.

## Allowed Files

May edit:

- only the production and test paths explicitly allowlisted by the assigned
  worker brief under `src/study_agent/` and `tests/`
- package exports within that same allowlisted boundary

May inspect:

- `src/study_agent/artifacts/`, `capabilities/`, `flashcards/`, `pedagogy/`,
  `playbooks/`, `ports/`, `prompts/`, `skills/`, `state/`, and `workers/`
- relevant specs, ADRs, tests, and worker profiles

Do not edit:

- files outside the task brief, files reserved by another active worker,
  `sbobby-web`, provider adapters, dependencies, or unrelated specs/docs

## Forbidden Decisions

Stop and report back before deciding:

- a new canonical event, reducer owner, persistence schema, or public StudyTool
- a new capability manifest/output contract or incompatible version change
- prompt/profile policy not already fixed by the bead and versioned skill
- provider/model selection, credential flow, dependency, or hosted queue
- whether an operational proposal becomes accepted or published state

## Quality Gates

- Every generated claim or artifact has exact source/evidence commitments and
  tampered, missing, reordered, or stale evidence fails closed.
- Behavior lives in versioned skills/playbooks/prompts; adapters remain technical
  and the core remains provider/model agnostic.
- Operational worker/checkpoint state never becomes canonical learner state, and
  compact host views do not leak transcript, credentials, provider metadata, or
  unverified detail.
- Codecs and fingerprints are deterministic, bounded, domain-separated, and
  exact-decode when the bead defines a durable boundary.
- Focused unit/contract/integration tests, architecture/tool parity, Ruff, strict
  mypy, and `git diff --check` pass before handoff.

## Verification

Run the exact focused commands from the assigned bead and worker brief, then:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/architecture tests/contract/tools/test_public_tool_contract.py
.venv/bin/ruff check <allowed production and test paths>
.venv/bin/mypy --strict <allowed production and test paths>
git diff --check
```

If verification cannot run, report the reason and the narrowest completed check.

## Report Format

Return:

- files changed;
- behavior and versioned contracts implemented;
- grounding, isolation, and provider-neutrality evidence;
- exact verification commands and results;
- profile constraints followed;
- unresolved questions and recommended review or next bead.
