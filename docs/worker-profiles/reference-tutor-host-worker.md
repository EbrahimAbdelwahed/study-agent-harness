# Worker Profile: reference-tutor-host-worker

## Reuse Trigger

Use this worker for provider-neutral tutor-host orchestration, trusted host
authority seams, operational continuation state, and host-owned file capture
that compose existing harness owners without changing study behavior.

## Mandate

Implement one bounded external-host slice exactly as specified while preserving
the capability gateway as the sole skill/playbook lifecycle owner and the
canonical event services as the sole study-state writers.

## Scope

In scope:

- Provider-neutral host runner contracts and orchestration.
- Exact mapping of existing capability gateway outcomes and retryable errors.
- Trusted authority/action identity supplied through injected host ports.
- Operational continuation or file-snapshot registries behind narrow byte-store
  ports.
- Immutable text/Markdown capture through existing source-input contracts.
- Strict codecs, bounded views, redaction, retry, interruption, stale refresh,
  expiry, tamper, and restart tests owned by the assigned bead.

Out of scope:

- Tutor pedagogy, capability selection policy, new skills/playbooks/manifests,
  canonical learner state, recall policy, prompts, model adapters, UI, CLI,
  network/provider SDKs, auth/subscription behavior, PDF/OCR/audio, or
  `sbobby-web`.
- Adding a StudyTool, arbitrary tool call, generic workflow DSL, model-authored
  authority, or a second capability lifecycle.

## Required Context

Read first:

- `AGENTS.md`
- `docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md`
- assigned TUT-06 bead and worker brief
- `src/study_agent/hosts/contracts.py`
- `src/study_agent/hosts/context.py`
- `src/study_agent/ports/tutor_host.py`
- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/gateway.py`
- for file work: `src/study_agent/ports/source_input.py`,
  `src/study_agent/adapters/filesystem/source_input.py`, and
  `src/study_agent/ingestion/service.py`

Current-doc research:

- Not needed for TUT-06B/C. Required before TUT-06D because the OpenAI Responses
  API is temporally unstable.

## Allowed Files

May edit:

- `src/study_agent/hosts/`
- bead-approved new modules under `src/study_agent/ports/`
- bead-approved technical adapters under `src/study_agent/adapters/`
- the exact capability outcome/gateway files named by an approved brief
- focused tests under `tests/unit/hosts/`, `tests/contract/hosts/`,
  `tests/integration/`, and `tests/architecture/`
- assigned bead, worker brief, log, and handoff after behavior is approved

May inspect:

- all `src/study_agent/` and `tests/` patterns needed to reuse owners

Do not edit:

- `src/study_agent/domain/`, `state/`, `skills/`, `playbooks/`, prompts,
  capability manifests/bindings, assessment/artifact/recall owners, existing
  seven StudyTools, dependencies, `sbobby-web`, or unrelated docs/tests

## Forbidden Decisions

Stop and report back before deciding:

- any new public decision kind, StudyTool, capability, event/schema, dependency,
  provider branch, persistence technology, model-visible authority field, file
  format, role/trust policy, or automatic ingestion behavior;
- any change that requires the runner to inspect private gateway bindings or
  playbooks;
- any behavior that would expose exact continuation bytes, execution context,
  local paths, raw file bytes, credentials, grants, principal ids, retry ids, or
  provider configuration to `TutorDecisionPort`.

## Quality Gates

- Every effect has an interruption check immediately before and after it.
- Exact retry reuses the same trusted identity; changed content cannot collide.
- Gateway statuses/errors remain distinct and no non-success exposes completed
  output.
- Operational bytes have strict canonical codecs, bounds, owner binding,
  conflict detection, and restart tests.
- File paths and filesystem identity terminate at `SourceInputPort`; model views
  contain only allowlisted descriptors.
- No production behavior outside the allowed files changes.

## Verification

Run:

```bash
PYTHONPATH=.:src .venv/bin/python -m pytest -q <focused tests>
.venv/bin/ruff check <changed files>
MYPYPATH=src .venv/bin/mypy --strict <changed files>
git diff --check
```

If verification cannot run, report the reason and the narrowest manual check
completed.

## Report Format

Return:

- files changed;
- exact public types and JSON/identity shapes added or changed;
- behavior and acceptance criteria implemented;
- verification commands and results;
- confirmation that every forbidden boundary was preserved;
- unresolved questions or follow-up bead needed.
