# Worker Brief: AML-05 production

## Assignment

Implement the production half of `AML-05` from
`specs/agent-managed-lifecycle/slices/05-manifest-contract.md`.

## Read First

- `specs/agent-managed-lifecycle/README.md`
- `specs/agent-managed-lifecycle/slices/05-manifest-contract.md`
- `specs/agent-managed-lifecycle/beads/05-manifest-contract.md`
- `docs/decisions/ADR-0003--agent-operated-management-plane.md`
- current repository config, canonical JSON, CLI registry and error mapping

## Scope

You may change:

- `src/study_agent/repository_config.py`
- `src/study_agent/cli/config.py`
- mechanical config imports in `src/study_agent/cli/__init__.py`, `main.py`,
  `repository.py`, and `registry.py`
- `src/study_agent/lifecycle/__init__.py`
- `src/study_agent/lifecycle/contracts.py`
- `src/study_agent/adapters/filesystem/lifecycle.py`
- `src/study_agent/cli/registry.py`
- `src/study_agent/cli/commands.py`

Do not change tests, specs/docs, domain events, projections, stores, course/source/
session services, model adapters, skills/playbooks, or any slice 06–09 behavior.
Do not commit or push.

## Invariants

- Event-sourced state remains canonical; the manifest is operational intent only.
- Parsing/canonicalization are pure. The filesystem adapter reads only the exact
  manifest path, bounded with max+1 detection, `O_NOFOLLOW`, regular-file
  `fstat` before/after and stable identity; declared paths remain unopened lexical values.
- Reuse the neutral technical config owner. Never duplicate provider config,
  credential, secret-field, or canonical JSON policy.
- No manifest/model argument can select authority, capabilities, identity,
  idempotency, skills, playbooks, prompts, tools, plugins, imports or commands.
- Exact seven StudyTools and `agent-operations@1` stay unchanged.
- No new dependency.

## Requirements

- Implement the exact closed fields, nullability, bounds and canonical ordering
  from slice 05 using frozen/slotted values.
- Decode strict bounded UTF-8 JSON with duplicate-key/non-finite rejection and
  safe `RecursionError` handling.
- Validate arbitrary `model.settings` iteratively: depth 16, 1,024 total nodes,
  256 members/container, 128-character keys and 4,096-character strings.
- Reject non-relative/dot/traversing paths lexically without normalization or I/O.
- Fingerprint `sha256(b"study-agent-lifecycle-manifest-v1\\0" + canonical_bytes)`.
- `manifest schema` has no file I/O. `manifest validate [PATH]` defaults exactly
  to `./study-agent.manifest.json` and returns only version/fingerprint/counts.
- Enforce the existing 64 KiB repository-config size before serialization output.

## Verification

Run Ruff and strict mypy on production plus any existing relevant config/CLI
tests. Report files, exact contract, gates and unresolved risks.

## Report Back

Return changed files, behavior, exact commands/outcomes and any decision that
would expand scope. Do not silently weaken a normative bound.
