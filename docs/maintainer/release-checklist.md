# Source release candidate checklist

This checklist verifies the `0.2.0` alpha source candidate. It does not authorize
a push, tag, package upload, GitHub release, or any other external action.

## Candidate state

- [ ] Confirm `pyproject.toml`, `study_agent.__version__`, README, changelog, and
  security policy agree on `0.2.0` alpha.
- [ ] Confirm `git status --short` contains no unintended files and
  `git diff --check` passes.
- [ ] Stage release files by explicit path; do not use `git add -A` in a dirty
  checkout or include local duplicate/lock files by accident.
- [ ] Confirm the maintained release surface and built artifacts contain no
  private product names, credentials, absolute user paths, or private study
  material.
- [ ] Confirm recall remains explicitly unavailable and no historical API,
  scheduling, PDF, browser-shell, or product module entered the core.

## Offline quality gates

From the candidate checkout:

```bash
.venv/bin/python -m pip install -e '.[dev]' build
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python -m build --wheel --sdist --outdir dist
.venv/bin/python -m pytest tests/quality
```

Record the exact versions and outcomes. Default verification must not require a
credential, provider SDK, model call, or network access.

## Clean-install proof

Install the wheel into an empty Python 3.12 or 3.13 environment and run:

```bash
study-agent --version
study-agent --help
study-agent-demo --json
study-agent --json describe
study-agent --json operator skill --output ./study-agent-operator/SKILL.md
```

Also import `study_agent` and `study_agent.tools`, and run
`docs/examples/external_agent.py` with `STUDY_AGENT_BIN` pointing to the
clean-installed executable. Inspect both wheel and source-distribution contents
using the repository quality tests.

## Maintainer-only publication

Publication requires a separate version decision, registry ownership and
provenance review, protected credentials or trusted publishing, final human
approval, and explicit authorization for each external action. Published files
cannot be replaced; on failure, fix forward with a new version rather than
reusing an uploaded version.
