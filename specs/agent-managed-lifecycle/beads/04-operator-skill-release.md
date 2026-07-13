# Task Bead: AML-04 operator skill and 0.1.1 release

Status: Complete
Priority: P1
Type: task
Depends On: AML-02, AML-03

## Worker Profile

reuse `implementer`, then blind unprimed evaluator and `reviewer`

Rationale:

The production seam is fixed, while the skill must be forward-tested by an
agent that does not inherit implementation context.

## Context

The 0.1.1 primitives are agent-operable but an installed generic agent still
needs one versioned, packaged workflow for discovery, setup, population,
verification, stable-session retry, and export.

## What To Do

- Package the sole `SKILL.md` resource under `study_agent.operator_skill`.
- Add stable identity/version/fingerprint and offline extraction receipt.
- Register `operator skill --output PATH` and expose its metadata in describe.
- Update the external-agent example and README agent quickstart/retry contract.
- Bump package/runtime version to 0.1.1.
- Add wheel/resource/extraction/empty-directory journey tests and CI checks.
- Run a blind skill eval from a fresh, unprimed agent context.

## Likely Files / Packages

- `src/study_agent/operator_skill/`
- `src/study_agent/cli/registry.py`, `commands.py`
- `pyproject.toml`, `.github/workflows/ci.yml`
- `docs/examples/external_agent.py`, `README.md`
- `tests/contract/cli/`, `tests/integration/`

## Acceptance Criteria

- [x] Installed wheel contains one canonical skill resource and `py.typed`.
- [x] Extraction is byte-identical and checksum-verified offline.
- [x] Describe exposes non-null stable operator-skill metadata.
- [x] Skill prescribes discover → init → populate → doctor → stable session →
      optional ask/retry → export, plus 0.2 status/plan/apply recovery.
- [x] Blank-project agent journey succeeds without credentials/network.
- [x] Python 3.12/3.13 CI covers build/install/extract smoke.
- [x] Version reports 0.1.1 consistently.

## Verification

- `python -m pytest`
- `python -m ruff check .`
- `.venv/bin/python -m mypy`
- `python -m build --wheel --sdist --outdir dist`
- clean venv install, CLI discovery/extraction/journey smoke
- skill creator `quick_validate.py`

## Out Of Scope

- Slice 05+ desired-state lifecycle implementation, new StudyTools, provider
  branches, prompts, pedagogy, retrieval ranking, hosted/product surfaces.

## Notes / Handoff

- The Python resource directory is fixed by the approved spec as
  `study_agent/operator_skill`; the skill frontmatter ID remains hyphenated.
