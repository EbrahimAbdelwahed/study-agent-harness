# Context Pack: Harness Package Foundation

Date: 2026-08-09
Run ID: `20260809-harness-package-foundation`
Project: `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration`

## Purpose

This pack gives the orchestrator and future workers enough repository context to create a precise spec and scoped task graph.

## Files Read

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `docs/archive/build-week/README.md`
- `docs/archive/build-week/proof/README.md`
- `specs/package-foundation/README.md`
- `CONTEXT.md`
- `CONTEXT-MAP.md`
- `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`

## `AGENTS.md`

```text
# AI Agent Instructions

Study Agent Harness is an embeddable, provider-neutral study runtime. Preserve
its canonical state, source-grounding, replay, approval, and recovery contracts.

## Required Git Workflow

- Treat the primary checkout and shared worktrees as read-only.
- Every task that changes files must use a dedicated Git worktree and a
  `codex/<task>` branch. Do not create a nested worktree when the task is already
  running in its own dedicated worktree.
- Start ordinary work from the latest `origin/main`. Use another base only when
  the task explicitly requires integration or recovery from that lineage.
- Inspect `git status` and `git worktree list` before editing. Never overwrite,
  stash, commit, or clean changes that belong to another user or agent.
- Keep commits intentional and reviewable. Do not mix unrelated changes.
- Run the narrowest relevant verification first, followed by broader project
  gates when practical.
- Push the task branch and open a pull request targeting `main` after
  verification. Never push directly to `main`.
- If push or pull-request creation is unavailable, stop with a verified local
  branch and commits ready, and document the exact blocker.

## Engineering Rules

- Be conservative with existing behavior and public contracts.
- Search the codebase and existing `dev/` memory before designing or editing.
- Prefer small, modular changes. Do not refactor unrelated code.
- Do not introduce dependencies unless they materially reduce risk or
  complexity. Keep provider, parser, scheduler, and observability integrations
  optional when possible.
- Canonical facts and human decisions belong to the harness. Model output is
  untrusted and cannot silently approve itself or mutate canonical state.
- Keep provider transports, persistence adapters, UI, and policy owners behind
  explicit ports. Do not leak their types into neutral domain contracts.
- Preserve deterministic replay: model calls and operational logs are not
  canonical state.
- Never hardcode credentials. Use environment references or host-provided secret
  resolvers.

## Natural-Language Processing

- The repository default for summarization, extraction, classification,
  rewriting, flashcard generation, quiz generation, explanations, semantic
  transformation, study assistance, and search enrichment is `gpt-5.6-luna`.
- Route model calls through dedicated adapters and `OPENAI_API_KEY` environment
  references. Do not use the `gpt-5.6` family alias.
- UI and domain components must not call model APIs directly.
- Prompts that affect study outputs must be versioned or documented and covered
  by loading, error, and evaluation paths.

## Development Memory

- Read `dev/index.md` when present, then search `dev/plans/`, `dev/logs/`,
  `dev/notes/`, `dev/decisions/`, and `dev/handoffs/` for relevant context.
- Create a plan before multi-file, architectural, uncertain, integration, or
  high-risk work.
- Record exact verification commands and outcomes in a log when work completes,
  fails, or remains partial.
- Create a handoff when work remains incomplete or context must carry forward.
- Keep memory granular and use
  `YYYY-MM-DD-HHMM--area--task--type.md` filenames.

## Verification

- Prefer the project commands declared in `pyproject.toml` and CI.
- Run focused tests before the full suite.
- Validate lint, strict typing, tests, and package build for substantive changes.
- Document pre-existing failures without hiding or weakening them.
- After medium-risk changes, obtain one independent semantic correctness and
  regression review. Use a security review for untrusted input, filesystem,
  networking, credentials, or sensitive serialization.
```

## `README.md`

```text
# Study Agent Harness

`study-agent-harness` is an alpha Python library and reference CLI for building
source-grounded study agents. It provides a local, provider-neutral execution
core: the host supplies trusted authority and the model may propose only
schema-bounded actions.

The harness is designed to sit behind different agent hosts, models, providers,
and user interfaces without making any of them canonical. It has no runtime
dependency on a hosted product or agent SDK.

## Core principles

The append-only domain event stream is canonical state. Course, source, session,
artifact, assessment, and knowledge projections are derived read models. SQLite
checkpoints, the lexical index, local configuration, and filesystem layout are
operational state: they support recovery and performance but do not redefine the
study record.

Versioned skills describe capabilities, and playbooks compose study behaviour.
Model adapters translate technical protocols only; they do not own prompts,
policy, authority, or domain state. An embedding host creates trusted execution
context separately from model-proposed tool arguments.

The architectural rationale and compatibility rules are recorded in
[`docs/decisions/`](docs/decisions/). The original v0.1 specifications remain in
[`docs/specs/`](docs/specs/) as design history.

## Install

Python 3.12 or newer is required. The core runtime uses only the standard
library.

CI verifies Python 3.12 and 3.13 on Ubuntu. Other operating systems are expected
to work, but are not yet a release-support promise.

From a checkout:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
study-agent --version
study-agent --help
```

Development tools are isolated in an optional extra:

```bash
python -m pip install -e '.[dev]'
```

## First offline workflow

The core is an installed library and CLI, not a server. Create a local
repository, add a course and a UTF-8 Markdown source, then verify replay and
retrieval without credentials or network access:

```bash
study-agent init ./my-study-repository
cd ./my-study-repository
printf '# Example notes\nThe aortic valve opens into the aorta.\n' > notes.md
study-agent --repository . course create \
  --course-id example-course \
  --title "Example course" \
  --learning-goal "Explain the core concepts"
study-agent --repository . source add example-course notes.md \
  --source-id example-notes
study-agent --repository . doctor
```

`doctor` should report `status: ok`, `event_replay: ok`, and
`retrieval_rebuild: ok`. The default repository has no model configured, so
replay, retrieval, export, and diagnostics remain offline. `ask` requires an
explicitly configured model adapter.

Command help is the source of truth for arguments. Add the global `--json` flag
for a single machine-clean success or safe error document on stdout.

## Public integration points

There are two supported alpha entry points:

- `study-agent` is the reference process boundary. Run
  `study-agent --json describe` to discover commands, effects, retry guidance,
  tool manifests, contract versions, and unavailable capabilities.
- `study_agent.tools` is the low-level Python integration surface for immutable
  tool contracts, manifests, schema validation, trusted owner composition, and
  `StudyToolRegistry` invocation.

The [integration guide](docs/integrations.md) explains how an agent host binds
trusted execution context and canonical service owners without duplicating
business logic. The [external-agent example](docs/examples/external_agent.py)
demonstrates the installed CLI boundary without depending on an agent SDK.

This is not yet a general-purpose stable Python SDK. Repository composition is
a reference implementation, not a promised top-level facade. Recall scheduling
is available through the optional `recall` extra and reports an explicit
availability state when its policy adapter is not configured.

### Agent-operated setup

Automation should negotiate the machine contract and extract the versioned
operator workflow from the installed distribution:

```bash
study-agent --json describe
study-agent --json operator skill \
  --output ./agent-skills/study-agent-operator/SKILL.md
```

Verify the extracted file against the fingerprint returned by `describe`. Use
stable course, source, session, and idempotency identities. For `ask`, supply an
explicit `--session-id` and `--idempotency-key`; after lost output, retry the
same question with the same identities.

For desired-state setup, lifecycle manifests provide validation, planning, and
fingerprint-gated application while leaving canonical mutations with their
existing services:

```bash
study-agent --json manifest validate study-agent.manifest.json
study-agent --json manifest plan study-agent.manifest.json
study-agent --json manifest apply study-agent.manifest.json \
  --expect-plan PLAN_SHA256
```

Initialization is a separate first convergence step. Replan after any manifest,
source, or canonical-state change.

## Bundled offline demo

Run the deterministic tutor-host trace from any directory:

```bash
study-agent-demo "I have ten minutes. Help me understand heart valves."
```

The demo uses a bundled sanitized Markdown fixture and an in-process recorded
provider response. It exercises the real tutor runner, trusted-context boundary,
evidence refresh, and suspension/resumption contracts without an API key, model
SDK, local repository, or network call. Add `--json` for its inspectable trace.

It is a contract demonstration, not a live-provider benchmark and not a
substitute for the repository workflow above.

## Models and credentials

The bundled network adapter speaks an OpenAI-compatible HTTP protocol. Its
configuration stores technical values plus the name of a credential environment
variable. The credential value is read only when the repository is opened and
is never written to repository configuration.

Never put an API key in a model setting, committed file, transcript, fixture, or
export. Use `study-agent init --help` for adapter configuration. The
[reference tutor-host guide](docs/reference-tutor-host.md) documents optional
provider-backed execution, privacy behaviour, retries, costs, and limitations.

## Recovery and portable export

Recovery starts from current evidence: inspect status, obtain a fresh plan, and
apply only its reported fingerprint. Source ingestion commits the canonical
revision before rebuilding the discardable retrieval index; an index failure is
reported as a recoverable operational error rather than concealed or rolled
back.

Export is a deterministic, credential-free view of canonical course state.
Repeated exports at the same event high-water mark are byte-identical. The
allowlisted bundle excludes credentials, provider payloads, host paths, run
checkpoints, blob references, and source bytes. Its manifest is an integrity
boundary; the event stream remains the recovery boundary.

## Verify a checkout

Run the offline quality gates:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
```

Release acceptance additionally requires wheel and source-distribution content
checks, a clean-wheel install, CLI/demo/discovery/operator-skill smokes, and the
external-agent example. The exact local procedure lives in the
[release checklist](docs/maintainer/release-checklist.md).

Network smoke tests are opt-in. Default tests must not require credentials, a
provider SDK, or a hosted service.

## Context and roadmap

The canonical glossary and implemented invariants live in
[`CONTEXT.md`](CONTEXT.md). [`CONTEXT-MAP.md`](CONTEXT-MAP.md) separates current
behavior, approved target, and implementation gaps. [`ROADMAP.md`](ROADMAP.md)
is the single public home for ordered future work and non-goals.

## Status and project policies

Version 0.2.0 is alpha software and its public API is not stable. This checkout
is being prepared as a source release candidate; this work does not create a
tag, publish a package, or make an online release.

The project is available under the [Apache License 2.0](LICENSE). See
[`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md),
[`SUPPORT.md`](SUPPORT.md), and [`GOVERNANCE.md`](GOVERNANCE.md) for project
policies, and [`CHANGELOG.md`](CHANGELOG.md) for release-facing changes.

The original Build Week submission material is preserved under
[`docs/archive/build-week/`](docs/archive/build-week/README.md). It is historical
evidence, not current installation or release guidance.
```

## `pyproject.toml`

```text
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "study-agent-harness"
version = "0.2.0"
description = "Provider-neutral, event-sourced study-agent harness"
keywords = ["study agents", "tutoring", "event sourcing", "replay"]
readme = "README.md"
requires-python = ">=3.12"
license = "Apache-2.0"
authors = [{ name = "Ebrahim Abdelwahed" }]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "Topic :: Software Development :: Libraries",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Typing :: Typed",
]
dependencies = []

[project.urls]
Homepage = "https://github.com/EbrahimAbdelwahed/study-agent-harness"
Documentation = "https://github.com/EbrahimAbdelwahed/study-agent-harness#readme"
Changelog = "https://github.com/EbrahimAbdelwahed/study-agent-harness/blob/main/CHANGELOG.md"
Issues = "https://github.com/EbrahimAbdelwahed/study-agent-harness/issues"
Source = "https://github.com/EbrahimAbdelwahed/study-agent-harness"

[project.scripts]
study-agent = "study_agent.cli.main:main"
study-agent-demo = "study_agent.demo.anatomy:main"
study-agent-shell = "study_agent.demo.product_shell:main"
study-agent-shell-web = "study_agent.demo.browser:main"

[project.optional-dependencies]
dev = [
  "mypy>=1.15",
  "pytest>=8.3",
  "ruff>=0.11",
]
openai = ["openai>=2.46,<3"]
recall = ["fsrs==6.3.1"]
pdf = ["pypdf==6.14.2"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
study_agent = ["py.typed"]
"study_agent.demo" = ["fixtures/*.md", "browser.html"]
"study_agent.operator_skill" = ["SKILL.md"]

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
pythonpath = ["src", "."]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
```

## `docs/archive/build-week/README.md`

```text
# Build Week archive

This directory preserves the lightweight historical record of the OpenAI Build
Week work that led to Study Agent Harness. It is an archive, not the current
product guide.

- `proof/`: static, locally inspectable launch-proof pages.
- `plans/`, `logs/`, and `handoffs/`: contemporaneous planning and execution
  record.
- The remaining files: submission narrative, captions, narration, and montage
  material.

The original media are intentionally kept in a separate, non-versioned archive.
They were moved on 2026-08-02 without transcoding or deletion. The following
SHA-256 values identify the large deliverables independently of their local
storage path:

```text
1564a37b6ff6c1188844e169e98eeaccfbf39d3c5e2aae76e523e6ad88f71bfa  Study Agent Harness - Launch Video with Chunked Voiceover.mp4
0955a3af662e78528fa6a8a48cbbec6d0f1f8384253f20c89bb6a3c1bf6d88e3  Study Agent Harness - Launch Video with Voiceover - Slow Backup.mp4
67b808756f223a17b2bc6b40c98dc6dfc8da901219e510ef039a16d37765d62e3  video/study-agent-build-week-presentation-final-silent.mp4
d051aebf3f1dee91bfdd9c4a61bf84f51c71471a862699c7dccc600b36437947  Study Agent Harness - Launch Video under 3 Minutes.mp4
fc2fae9fa35e37dc6d5e62f6c63b2e6b7bb12fb5383d945a4b90ba3696091d0f  Study Agent Harness - Launch Video with Voiceover.mp4
a2e0aae0c90b26158209cd434e5affc24d97cbdd2a8078710937878e8004fb31  Study Agent Harness - Launch Video.mp4
816fa20b1c370e7cc18133bc2ede126a0ff1339deae337ba3f8c32b1deb834c6  Study Agent Harness - Voiceover Jerry B.mp3
```

Historical documents may retain their original `docs/build-week-*` or `output/`
paths as contemporaneous evidence; the archive locations above are canonical.
```

## `docs/archive/build-week/proof/README.md`

```text
# Build Week launch proof

This is a local, non-product visualizer for the deterministic offline anatomy
trace. Its displayed source, evidence, context, status, and parity values are a
checked-in projection of:

```bash
study-agent-demo --json
```

Serve this directory with a static HTTP server. The default view plays an
80-second, six-chapter sequence designed for the cue windows in
`docs/archive/build-week/build-week-narration-final.txt`. `?scene=1` through `?scene=6` freeze the
corresponding chapter for deterministic visual QA.

The proof is a product-direction visualization backed by the real offline trace.
It does not call a provider or add a new harness contract.

The optional Codex + Flywheel companion is `flywheel-index.html`. It plays a
deterministic 39-second, six-chapter trace of how the project used Codex:
human-approved spec → dependency-aware beads → bounded worker → real offline
CLI proof → risk-proportionate tests/reviews → durable handoff. It deliberately
uses a distinct demonstrative process interface, not the study-harness UI. Use
`?scene=1` through `?scene=6` to freeze a chapter for capture. Its terminal box
is a legible subset of the real `study-agent-demo` output; the labels and
evidence paths are projections of checked-in artifacts.
```

## `specs/package-foundation/README.md`

```text
# Harness Package Foundation

Status: Approved — specification materialized; implementation not started

Last updated: 2026-08-09

## Next Agent Prompt

Start with PF-01 and implement the public facade as a small, typed seam. Read
`CONTEXT.md`, `CONTEXT-MAP.md`, this README, and the selected slice before
editing. Implement one slice at a time, keep the public contracts below
frozen, run the slice verification, and update this section before ending your
pass.

Current pickup: PF-01 — Public manifest.

Active warnings:

- This specification owns package stabilization only. Job orchestration,
  workers, web evidence, sealed verification, and Decision Trace are later
  runtime work and must not enter these slices.
- The package base must remain standard-library-only. Provider, FSRS,
  filesystem, telemetry, and specialist integrations stay behind optional
  adapters or extras.
- Cardine is a downstream consumer. Harness code and this specification must
  not import or name Cardine product modules, auth, UI, or deployment code.

Implementation checklist:

- [ ] [PF-01 — Public manifest](slices/PF-01-public-manifest.md)
- [ ] [PF-02 — Failures and authority](slices/PF-02-failures-authority.md)
- [ ] [PF-03 — Events, upcasting, and module](slices/PF-03-events-upcasting-module.md)
- [ ] [PF-04 — Storage contract kit](slices/PF-04-storage-contract-kit.md)
- [ ] [PF-05 — Sources and citations](slices/PF-05-sources-citations.md)
- [ ] [PF-06 — Capabilities](slices/PF-06-capabilities.md)
- [ ] [PF-07 — Artifacts, assessments, and recall](slices/PF-07-artifacts-assessments-recall.md)
- [ ] [PF-08 — Async-first runtime](slices/PF-08-runtime.md)
- [ ] [PF-09 — Distribution](slices/PF-09-distribution.md)
- [ ] [PF-10 — Release](slices/PF-10-release.md)
- [ ] [PF-11 — Stable facade promotion](slices/PF-11-stable-facade-promotion.md)

Before ending each implementation pass, update the status, current pickup,
warnings, and checklist above with the observed verification result. Do not
create beads from this folder; the implementation orchestrator will create
them only after this contract is accepted.

## Goal

Publish a versioned `study-agent-harness` Python package with one curated,
provider-neutral `study_agent.api` facade. The foundation makes existing
event, source, capability, artifact, assessment, and recall behavior safe for
downstream use without introducing the future job kernel or product policy.
The first adoption artifact is a clean package boundary that Cardine can pin,
install, and consume through an anti-corruption adapter.

## Scope

In scope:

- a machine-readable public import manifest and root version/facade surface;
- a closed public failure taxonomy and host-supplied authority context;
- versioned event envelopes, deterministic upcasters, and immutable module
  registration;
- narrow storage, clock, ID, repository, blob, and replay ports plus a
  reusable offline contract kit;
- immutable source/revision/blob identity and citation resolution;
- explicit, namespaced, manifested, permissioned capability registration;
- generic artifact proposal/revision/decision lifecycle, assessment ledger
  contracts, and recall/scheduling ports;
- dependency-injected async runtime services with a sync convenience facade;
- package namespace, entry-point, optional-extra, and wheel/sdist boundaries;
- release evidence and semver gates for the first Cardine adoption pin.

Out of scope:

- durable Job/lease/retry/queue orchestration or a generic workflow engine;
- workers for hierarchical flashcards, web evidence, or sealed verification;
- Decision Trace or remote telemetry; these belong to the future runtime spec;
- Cardine curriculum, authority/currency/integrity policy, learner model,
  readiness, planning, UI, auth, deployment, or product commands;
- a hosted service, organizations, billing, sharing, or cross-user approvals;
- a Pi/runtime dependency, vendored agent framework, provider-specific core,
  arbitrary network fetch, or mandatory third-party dependency;
- a permanent compatibility bridge for copied Cardine `study_agent` modules.

## Ownership and invariants

- Harness owns portable mechanisms, schemas, transitions, validation, replay,
  and trust boundaries. Cardine owns academic meaning and product policy.
- The append-only per-course event stream is canonical. Projections,
  snapshots, indexes, caches, runs, and diagnostics are rebuildable or
  operational and never independent authorities.
- Models and providers supply transport or proposals only. They cannot mint
  identity, grants, scopes, policy, parentage, approvals, or canonical
  outcomes.
- Only a Host creates principals, grants, and scopes. `HUMAN` represents an
  authenticated owner, `SERVICE` represents authorized injected policy, and
  `MODEL` is untrusted and cannot approve or commit durable effects.
- Unknown, malformed, stale, unauthorized, conflicting, or ungrounded input
  fails closed. Adapter exceptions are translated at the facade.
- Durable commands carry idempotency keys. Equal key plus equal canonical
  input converges on the prior result; equal key plus different input is a
  conflict. Cancellation is cooperative before commit and never rolls back a
  committed event.
- Sources are immutable and content-addressed. A source revision, normalized
  substrate, citation, and derived projection have separate identities.
- Generated artifacts remain proposals until an explicit authorized decision.
  Generic lifecycle contracts never infer Cardine artifact kinds or policy.
- Public service surfaces are async-first where execution may suspend. A sync
  facade calls the same async implementation and is not a second runtime.
- Harness never imports Cardine. The public facade exposes opaque host IDs for
  curriculum, objective, profile, and other product-owned references.

## Public package contract

The package distribution is `study-agent-harness`; the sole regular runtime
namespace is `study_agent`. The curated public boundary is:

```text
study_agent
  ├── __version__
  └── api
      ├── runtime
      ├── authority
      ├── storage
      ├── sources
      ├── capabilities
      ├── artifacts
      ├── assessments
      └── recall
```

`study_agent.api` publishes an immutable `PublicManifest` with facade version,
package version, subfacade names, exported symbols, schema versions, and
supported Python versions. Importing the root package must not import model,
provider, UI, CLI, filesystem, FSRS, or optional-extra modules. Internal
modules remain implementation details without a semver guarantee.

Composition is explicit. A host supplies a principal, repository, storage
ports, clock, ID factory, model adapter, and policy through one immutable
dependency bundle. No global locator, singleton, import-time registration, or
environment-driven auto-configuration is part of the foundation.

The base install has no mandatory dependencies beyond Python 3.12/3.13
standard library. SQLite is a built-in adapter. OpenAI, FSRS, PDF, telemetry,
and other integrations are optional extras or host-owned adapters.

## Slice graph

| Slice | Seam | Depends on | Independently observable result |
| --- | --- | --- | --- |
| PF-01 | `study_agent.api` manifest and root facade | — | Import manifest test passes without implementation imports |
| PF-02 | failure taxonomy and `AuthorityContext` | PF-01 | Safe typed failures and actor/grant checks |
| PF-03 | event envelope, upcasters, `KernelModule` | PF-01, PF-02 | Versioned append/replay and immutable module registration |
| PF-04 | storage/blob/replay ports and contract kit | PF-01..PF-03 | SQLite/filesystem/memory adapters pass shared contracts |
| PF-05 | source/revision/citation ports | PF-03, PF-04 | Content-addressed source and citation round trips |
| PF-06 | capability manifests and registry | PF-01..PF-04 | Explicit trusted registration and fail-closed dispatch |
| PF-07 | artifact, assessment, and recall facades | PF-03..PF-06 | Proposal/ledger/due-view replay contracts remain portable |
| PF-08 | async runtime and sync wrapper | PF-01..PF-07 | Same runtime serves async and sync host calls |
| PF-09 | package/namespace/entry-point boundary | PF-01, PF-06, PF-08 | Harness co-installs with a positive synthetic downstream fixture; the copied pre-adoption Cardine artifact is rejected by the negative fixture; actual Cardine co-install remains CA-04/CA-10-only |
| PF-10 | adoption release evidence and semver gates | PF-01..PF-09 | Clean artifacts, offline gates, and an exact `0.3.0` adoption pin |
| PF-11 | stable facade promotion | PF-10 + signed/hashed CA-08 installed-parity evidence | An executable evidence-only gate promotes the curated facade to `1.0.0`; it has no Cardine import or test dependency |

PF-01 through PF-04 establish the kernel boundary. PF-05 through PF-07
stabilize existing domain families. PF-08 composes them without adding
autonomous planning. PF-09 and PF-10 are distribution/release gates, not new
domain behavior. PF-11 is a post-adoption compatibility-evidence gate and
does not add runtime behavior.

## Review map

Human review is required at these non-blocking checkpoints during implementation:

- PF-01: inspect the import manifest for accidental private exports or eager
  optional imports.
- PF-02/PF-03: inspect authority and event ownership for model write paths,
  unsafe adapter errors, and duplicate canonical facts.
- PF-04/PF-05: inspect replay, blob immutability, citation binding, and path
  ownership; verify no derived text can act as primary evidence.
- PF-06/PF-07: inspect plugin registration, proposal approval boundaries,
  opaque Cardine references, and recall policy ownership.
- PF-08: inspect dependency injection and prove sync calls delegate to the
  async implementation.
- PF-09/PF-10: inspect wheel/sdist contents, entry points, dependency metadata,
  Python matrix, and the positive/negative side-by-side installation cycle.
- PF-11: inspect the signed/hashed CA-08 installed-parity evidence, exact
  `1.0.0` promotion record, and the absence of Cardine imports/tests in the
  Harness gate.

Each checkpoint is non-blocking for implementation progress. The implementing
agent records the evidence and rationale in the slice log; silence is not a
reason to hold an otherwise verified slice.

## Cross-slice verification

The narrow checks in each slice are mandatory. The final foundation gate is:

```text
git diff --check
uv run --python 3.12 --extra dev ruff check src tests
uv run --python 3.13 --extra dev ruff check src tests
uv run --python 3.12 --extra dev mypy
uv run --python 3.13 --extra dev mypy
uv run --python 3.12 --extra dev pytest -q
uv run --python 3.13 --extra dev pytest -q
uv build --out-dir /tmp/study-agent-harness-package-foundation
```

The package must also pass a clean-wheel/sdist install smoke on Python 3.12
and 3.13, a base dependency-free install smoke, a public import-manifest
test, the reusable event/blob/replay/capability contract kit, and the PF-09
positive/negative co-install cycle. The positive fixture owns only `cardine`;
the copied pre-adoption Cardine artifact is a deliberate red fixture until
CA-04/CA-10 removes its `study_agent` package and legacy commands. Foundation
detects that collision rather than claiming to repair it. Actual Cardine
co-install/parity is CA-04/CA-10-only. CI installs the built artifact and
never a sibling checkout or `PYTHONPATH` injection.

PF-11 runs only after CA-08 has produced an installed-parity report. The
promotion command accepts a detached signature and SHA-256 commitments for
the report and the tested artifacts, verifies them against the declared trust
input, and writes a `1.0.0` facade-promotion record. It consumes no Cardine
module, source tree, or Cardine test; orchestration records the evidence
outside the Harness package.

## Resolved implementation notes

The following details are intentionally left to the owning slice because they
do not alter the approved public contract: exact private module factoring,
fixture directory names under `tests/contract`, whether a synchronous adapter
uses a worker thread internally, and the text of release notes. A slice may
settle these details locally while preserving its exact types, failure
semantics, ownership, and verification commands. Any new cross-package
boundary, dependency, schema, or public export requires returning to the
specification before implementation continues.
```

## `CONTEXT.md`

```text
# Study Agent Harness Context

This is the concise vocabulary and invariant sheet for the harness. The
approved behavior is defined by the accepted decisions in
[`docs/decisions/`](docs/decisions/) and the current implementation in
[`src/study_agent/`](src/study_agent/); this file names the boundaries without
duplicating their registries.

## Vocabulary

- **Harness** — the provider-neutral, local-first execution layer. It owns
  schemas, transitions, validation, replay, and trust boundaries; it is not a
  hosted product or a chatbot UI.
- **Host** — the embedding application that supplies a principal, repository,
  session, model adapter, and storage, and that bounds the adaptive loop.
- **Kernel** — canonical domain state and generic lifecycle rules: event
  append, projections, capability dispatch, validation, proposals, approvals,
  jobs, and observability.
- **Capability** — a versioned, discoverable study operation with schemas,
  policy, validators, provenance, idempotency, and explicit write permissions.
- **Tool** — a callable interface exposed to a host or capability. The current
  registry includes both queries and a bounded note command. The approved
  target keeps queries directly callable and routes new durable effects through
  permissioned capabilities and proposals.
- **Worker** — an execution component for a bounded capability. Workers do not
  own canonical policy or state; they return validated results or proposals to
  the kernel.
- **Source** — immutable, content-addressed learner material. A source
  revision, normalized substrate, citation, and derived knowledge-base
  projection have separate identities.
- **Evidence** — source-bound support that retains citation, lineage, and trust
  information. Candidate web evidence is quarantined until admitted.
- **Artifact proposal** — a versioned generated study artifact awaiting an
  explicit decision. Generation and validation never imply acceptance.
- **Reference Exam** — an immutable, approved authentic past exam or
  teacher-authored simulation used as evidence about assessment style. It is
  never reused as learner-facing generated content.
- **Exam Profile** — an approved, versioned description of assessment scope,
  topic mix, question types, detail, and phrasing, derived from a syllabus and
  compatible Reference Exams.
- **Generation Plan** — the learner-visible proposal describing what a
  Synthetic Verification will generate and why, without revealing its sealed
  questions.
- **Synthetic Verification** — a novel, sealed assessment generated from an
  approved Exam Profile and Generation Plan. Its questions become visible only
  during an attempt.
- **Decision Trace (approved target)** — the canonical minimal record of
  observable choices, outcomes, validators, and transitions. It is an audit
  trail, not model chain-of-thought.
- **Operational state** — checkpoints, indexes, job leases, metrics, and
  diagnostic payloads used for recovery or debugging. It is not canonical
  learner truth.

## Implemented invariants

1. The append-only event stream is canonical; projections, snapshots, and
   indexes are rebuildable and never independent authorities.
2. Models and providers propose or translate transport. They cannot select
   identity, permissions, policy, parentage, or canonical outcomes.
3. Skills and playbooks are model-independent. The host owns bounded adaptive
   choice; the kernel owns capability execution and validation.
4. Unknown, malformed, stale, unauthorized, or ungrounded input fails closed.
   Retries are bounded and never silently mutate canonical history.
5. Sources remain immutable and citable. Derived synthesis preserves claim
   lineage and trust and never becomes a primary source.
6. Generated artifacts remain proposals until an explicit authorized decision;
   generation and validation do not imply acceptance.
7. The kernel is dependency-light and model-neutral. It has no Pi/runtime
   dependency or vendored agent framework; hosts bring adapters and storage.
8. Provider-neutral service surfaces are asynchronous where execution can
   suspend. The reference SQLite adapter is local and single-writer; worker
   execution remains behind ports.
9. Stored execution proofs describe observable inputs, outputs, validations,
   and transitions; they do not request or store private chain-of-thought.
10. A single learner approval boundary is in scope. Cross-user sharing,
    organizations, billing, hosted operations, and product UI are deferred.

## Approved target constraints

- A sync convenience API must wrap the same async implementation; it must not
  become a second runtime.
- Synthetic Verification content remains sealed until an attempt, and required
  coverage gaps block release.
- A canonical Decision Trace will record the observable path taken. Full
  redacted payloads remain diagnostic-local operational data, retained for 14
  days by default, with no default remote telemetry.

## Source owners

Use the owning module or decision rather than copying its roster here:

- Domain values and event contracts: [`src/study_agent/domain/`](src/study_agent/domain/)
  and [ADR-0002](docs/decisions/ADR-0002--event-state-skills-playbooks.md).
- Host boundary and capability gateway: [`src/study_agent/application/`](src/study_agent/application/),
  [`src/study_agent/capabilities/`](src/study_agent/capabilities/), and
  [ADR-0004](docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md).
- Immutable knowledge-base identity and replay: [`src/study_agent/knowledge/`](src/study_agent/knowledge/),
  [`docs/specs/kb-v0-2-retrieval-architecture.md`](docs/specs/kb-v0-2-retrieval-architecture.md),
  and [ADR-0014](docs/decisions/ADR-0014--kb-v02-identity-compatibility-and-replay.md).
- Artifact and pedagogical policy: [`src/study_agent/artifacts/`](src/study_agent/artifacts/),
  [`src/study_agent/assessments/`](src/study_agent/assessments/), and
  [ADR-0008](docs/decisions/ADR-0008--closed-pedagogical-profiles-and-artifact-proposals.md).
- Provider and persistence adapters: [`src/study_agent/adapters/`](src/study_agent/adapters/);
  they remain technical boundaries, not behavior owners.

For the ordered future work, see [`ROADMAP.md`](ROADMAP.md). For ownership and
current-versus-target status, see [`CONTEXT-MAP.md`](CONTEXT-MAP.md).
```

## `CONTEXT-MAP.md`

```text
# Study Agent Harness Context Map

This map shows ownership and approved boundaries. It distinguishes what is
implemented now from the target shape; it is not a copy of module rosters.
The accepted behavior sources are [ADR-0001](docs/decisions/ADR-0001--oss-harness-only.md),
[ADR-0002](docs/decisions/ADR-0002--event-state-skills-playbooks.md),
[ADR-0004](docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md),
[ADR-0008](docs/decisions/ADR-0008--closed-pedagogical-profiles-and-artifact-proposals.md),
and [ADR-0014](docs/decisions/ADR-0014--kb-v02-identity-compatibility-and-replay.md).

```mermaid
flowchart LR
  Host[Embedding host\nprincipal + bounds + adapters]
  Runtime[Harness runtime\nasync-first API]
  Kernel[Kernel\nevents + transitions + validation]
  Gateway[Capability gateway\ntrusted manifests + permissions]
  Sources[Immutable sources + KB\ncontent-addressed evidence]
  Jobs[Generic job lifecycle\nSQLite backend, Python executors]
  Workers[First-party workers\nflashcards, web evidence, verification]
  Models[Model/provider adapters\ntransport only]
  Trace[Decision Trace + ops telemetry]
  Decisions[Human/policy decisions\nproposal approval]
  Cardine[Future Cardine consumer\nversioned package]

  Host --> Runtime --> Kernel
  Kernel --> Gateway
  Kernel --> Sources
  Kernel --> Jobs --> Workers
  Host --> Models --> Runtime
  Workers --> Models
  Workers --> Sources
  Gateway --> Decisions
  Decisions --> Kernel
  Kernel --> Trace
  Runtime -. package boundary .-> Cardine
```

## Current

- The project is an Apache-2.0, provider-neutral Python harness with an
  event-sourced state kernel, immutable source/evidence contracts, a bounded
  `TutorHostRunner`, and a capability gateway. The implementation owners are
  [`src/study_agent/domain/`](src/study_agent/domain/),
  [`src/study_agent/application/`](src/study_agent/application/), and
  [`src/study_agent/capabilities/`](src/study_agent/capabilities/).
- KB v0.2 identity, compatibility, and replay rules are accepted; the
  knowledge package and its spec own details. See
  [`docs/specs/kb-v0-2-retrieval-architecture.md`](docs/specs/kb-v0-2-retrieval-architecture.md).
- Artifact proposals, closed pedagogical profiles, assessment contracts,
  recall, optional FSRS, capability-gap feedback, and local PDF/Markdown
  workarounds exist as bounded areas. Their source owners are the corresponding
  packages under [`src/study_agent/`](src/study_agent/) and the accepted ADRs.
- The reference CLI and browser are demonstration/reference hosts, not the
  production composition boundary. See [`src/study_agent/cli/`](src/study_agent/cli/)
  and [`src/study_agent/demo/`](src/study_agent/demo/).

## Approved Target

- Keep the kernel dependency-light and free of Pi/runtime vendoring. The host
  supplies model adapters and storage; the harness owns schemas, transitions,
  validation, and trust boundaries.
- Make the public API async-first, with a sync convenience wrapper over the
  same runtime. Tool registration is explicit; trusted plugins are namespaced,
  manifested, and permissioned.
- Keep read-only tools callable, while capabilities orchestrate durable effects
  through proposals and explicit human or injected policy decisions.
- Let the kernel own generic job/workflow lifecycle. SQLite is the durable
  built-in job backend and Python executors run work; a future distributed
  queue can implement the same port.
- Ship installable first-party workers for hierarchical flashcard generation,
  quarantined web evidence brokering, and sealed synthetic verification. A
  deterministic coordinator shards bounded work; review and deterministic
  assembly remain separate.
- Record an auditable canonical Decision Trace of the path taken. Keep full
  redacted payloads in diagnostic-local operational storage only, with no
  default remote telemetry and optional OpenTelemetry integration.
- Provide offline fixture evals and opt-in live comparisons against the
  recommended `gpt-5.6-luna` baseline. Candidate models, including DeepSeek V4
  Flash, are eval-gated rather than globally blocked.
- Publish a versioned package for downstream consumers such as Cardine; do not
  copy harness source into the product.

## Gap

- The local repository does not yet compose a real model → host runner →
  capability gateway path end to end; the current proof uses bounded/reference
  composition.
- The repository already contains retry-stable isolated worker orchestration,
  flashcard fan-out, and exam-analysis foundations. The gap is the target-grade
  durable job kernel, observability surface, and job-backed hierarchical
  flashcard, web-evidence, and sealed-verification compositions; existing
  SQLite adapters and operational stores do not provide that assembly yet.
- The browser shell remains an offline/reference surface. Online research stays
  a gap until a quarantined evidence port and admission flow are implemented.
- Sealed assessment generation, the separate coverage reviewer, and stale-input
  targeted regeneration require the approved workflow but are not a claim of
  complete production behavior today.
- Cross-user approvals and sharing remain out of scope; one learner approval
  boundary is the current contract.

See [`ROADMAP.md`](ROADMAP.md) for the public sequence and non-goals.
```

## `dev/handoffs/2026-08-09-2200--cardine-harness--specs-and-beads-design--handoff.md`

```text
# Handoff: Cardine / Study Agent Harness specs and beads design

Date: 2026-08-09 22:00
Area: Cardine, Study Agent Harness, package adoption, future implementation specs

## Current State

The user requested an overlap analysis between Cardine and Study Agent Harness,
followed by four execution-ready implementation specs and dependency-aware task
beads. The work is still in the grilling/decision-closure phase. No specs or
beads have been written yet.

The overlap analysis must use these documents as its semantic sources:

- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/CONTEXT-MAP.md`
- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/TECHNICAL-MAP.md`
- Cardine `/Users/ebrahimabdelwahed/Desktop/Dev/cardine/docs/domain/*/CONTEXT.md`
- Harness `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT.md`
- Harness `/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT-MAP.md`

Do not use old specs or beads as authority for the semantic overlap. They may
be inspected later as historical implementation material after ownership and
contracts are fixed.

## Skills and Process

- The active interview follows
  `/Users/ebrahimabdelwahed/.codex/skills/grilling/SKILL.md`.
- Spec materialization must follow
  `/Users/ebrahimabdelwahed/.codex/skills/write-spec/SKILL.md`.
- Beads and worker briefs must follow the dedicated repo-local skill and its
  templates:
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/skills/implementation-orchestrator/SKILL.md`
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/templates/task-bead.md`
  - `/Users/ebrahimabdelwahed/Desktop/Med/20_Progetti/study-agent-devkit/templates/worker-brief.md`
- Every bead must be executable without redesign or TBDs, fit one fresh context,
  produce an observable independently verifiable outcome, name spec coverage
  and grilling evidence, and declare worker profile, context, allowed scope,
  acceptance criteria, verification, dependencies, and out-of-scope behavior.
- Wide migrations use `expand -> migrate -> contract`; every temporary seam has
  an explicit removal bead.
- The user wants all architecture questions resolved before bead creation; do
  not create architecture-closure beads.

## Approved Four-Spec Structure

Exactly four main specs will be created:

1. Harness — Package Foundation.
2. Cardine — Harness Adoption.
3. Harness — Future Runtime Features.
4. Cardine — Future Product Features.

Each spec lives in its owning repository and contains its own slices/beads.
There is no fifth cross-repository spec. Cross-repository dependencies are
unidirectional:

```text
Harness contract bead -> released package/contract version -> Cardine adapter bead -> Cardine product bead
```

Harness must never depend on Cardine.

## Approved Ownership Boundary

- Harness owns provider-neutral mechanisms and portable contracts.
- Cardine owns academic meaning, product policy, composition, UI, auth, and
  deployment.
- Harness owns immutable source identity/revisions/blob/citation mechanics;
  Cardine owns educational authority, currency, integrity, notices, and
  curriculum alignment.
- Harness owns generic artifact proposal/revision/decision lifecycle; Cardine
  owns artifact kinds, approval policy, substantial-revision meaning, and
  product effects.
- Harness owns portable Reference Exam, Exam Profile, Generation Plan, and
  Synthetic Verification schemas/workflow; Cardine owns academic authenticity,
  exam components, attempts, criteria, grades, contests, and profile approval.
- Harness owns generic recall ledger, scheduling port, and due view; Cardine
  owns eligibility, rating meaning, substantial-revision effects, and mapping
  Retention Observations into Learner Model inputs.
- Cardine is the only planner. It owns Study Plan, Next Activity, rationale,
  mastery/readiness use, and learner overrides. Harness only validates and
  executes the selected bounded capability.
- Curriculum and Learner Model remain entirely Cardine-owned. Harness accepts
  opaque typed references such as concept, objective, and profile revision IDs.
- Domain Events are Cardine/product facts. Decision Trace is separate execution
  audit evidence. They link by correlation/causation IDs; no duplicate fact and
  trace does not feed mastery/domain projections.
- Shared contracts must not use bare `Evidence`: use `SourceEvidence`,
  `LearningEvidence`, `RetentionObservation`, and `CandidateWebEvidence`.

## Approved Package Direction

- Cardine will consume a versioned Study Agent Harness package; it will not keep
  an independently evolving copied core or a maintained source mirror.
- Harness retains the `study_agent` Python namespace exclusively.
- Cardine product code moves to `cardine`.
- Cardine imports Harness only through an anti-corruption/integration layer,
  recommended location `cardine.integrations.study_agent`; Cardine domain/UI/API
  expose Cardine DTOs rather than raw Harness objects.
- Cardine consumes stable library APIs only, not Harness CLI/browser/reference
  host composition.
- Migration order: Package Foundation -> Cardine adapter -> deterministic parity
  -> debug data reset -> copied-core removal -> future feature lanes.
- The Package Foundation stabilizes already-existing shared behavior only.
  Job kernel, workers, Decision Trace, web evidence, and sealed verification are
  Spec 3 and must not block removing the copied core.
- During adoption Cardine pins an exact package version/lock. After parity it may
  use a same-major compatible range, with every Harness upgrade represented by
  a verified Cardine bead.
- Semantic Versioning policy approved: curate an explicit public facade during
  `0.x`; release `1.0.0` after stable API/parity; thereafter MAJOR may break,
  MINOR is compatible functionality, PATCH is compatible bugfix.

## Approved Package Foundation Contracts

- Public API is a curated `study_agent.api` facade with typed subfacades for
  runtime, authority, storage ports, sources/citations, capabilities, artifacts,
  assessments, and recall. Root `study_agent` exposes version/facade only;
  internal modules have no SemVer guarantee.
- Composition is explicit dependency injection. Cardine/Host supplies principal,
  repository, storage, clock, ID factory, model adapter, and policy. No global
  locator, singleton, or hidden auto-configuration.
- Events use a versioned envelope containing event ID/type/schema version,
  aggregate or stream ID, timestamp, causation/correlation IDs, and validated
  payload. Deterministic upcasters can read supported old versions.
- Public failures use a typed closed taxonomy: validation, stale, unauthorized,
  conflict, not found, unavailable dependency, and internal failure. Provider,
  SQLite, and filesystem exceptions do not leak through the facade.
- Durable commands require idempotency keys. Same key/same input converges; same
  key/different input conflicts. Cancellation is cooperative before commit;
  committed events are not rolled back; retry occurs only from declared
  checkpoints.
- Capability/plugin registration is explicit, namespaced, manifested,
  permissioned, and versioned. No import-time/entry-point auto-discovery.
- Base package has no mandatory runtime dependencies beyond the standard
  library. SQLite remains built-in; provider, FSRS, OpenTelemetry, and specialist
  integrations are optional extras/adapters.
- Cardine registers product events/reducers/projections/services through an
  explicit immutable `KernelModule`. Collisions, unknown schemas, and late
  registration fail closed. Harness never imports Cardine.
- Ports are the main compatibility contract. Narrow first-party SQLite,
  filesystem blob, clock, and ID adapters are supported/documented consumers.
  Cardine owns paths and composition.
- Only the Host creates principals/grants/scopes: authenticated owner is HUMAN,
  authorized Cardine policy is SERVICE, provider is MODEL and can never approve.
  Cookies and browser credentials remain outside Harness events/DTOs/traces.
- Cardine deletes old `study-agent*` CLI aliases; only Harness owns those names.
  Cardine exposes only `cardine*` commands.
- Cardine product events and Harness-owned portable events share one per-course
  event store/sequence through KernelModule registration. Decision Trace is
  stored separately.
- Foundation release gates: clean wheel/sdist installs on Python 3.12/3.13;
  public import-manifest test; base dependency-free install; Ruff, strict mypy,
  full offline suite; reusable event/blob/replay/capability contract kit; no
  Cardine refs/product/auth/UI; simultaneous Harness+Cardine installation has no
  file or entry-point collision.
- Distribution direction approved: tagged PyPI wheel/sdist, first adoption
  release recommended as `0.3.0`, exact Cardine pin during adoption, `1.0.0`
  after parity/stabilization. CI installs the built/published artifact, never a
  sibling checkout or PYTHONPATH injection.

## Approved Cardine Adoption Contracts

- Use `expand -> migrate -> contract`:
  1. create `src/cardine` and new entry points;
  2. migrate composition root/UI/auth/settings/product behavior in green
     vertical slices;
  3. remove all temporary shims and Cardine-owned `study_agent` modules after
     import and parity gates pass.
- No external compatibility promise for old Cardine `study_agent` imports or
  `study-agent*` CLI aliases.
- Every copied/divergent file must be classified as: import from Harness; move
  to Cardine; upstream generic delta first; or temporary adapter with an explicit
  removal bead. No copied shared file remains at the end.
- Behavioral parity, not byte equality, is required before removal: same replay,
  identity/lineage, citation resolution, session/continuation recovery,
  artifact/assessment/recall outcomes, semantic export, and fail-closed stale/
  invalid/unauthorized behavior. UI may change without losing functionality.
- Existing Cardine canonical state is only debugging data and need not be
  migrated or preserved. There is no state migrator and no canonical dual write.
- Reset automatically removes known Cardine runtime data without pausing for
  user confirmation. The implementation resolves and validates exact targets
  first, then removes canonical, derived, and operational debug data while
  preserving versioned fixtures/code and original external source files.
- Known repository data paths from the audit are `study-agent.json`,
  `state/events.sqlite3`, `state/runs.sqlite3`, `state/retrieval.sqlite3`,
  `blobs/`, and `exports/`. Blob deletion destroys internally imported source
  content, which is authorized because this repository state is disposable.
- Do not keep a permanent broad destructive `reset --all` command merely for
  this migration.
- No implementation-time confirmation is allowed for the authorized debug-data
  reset; it must not block the agent.

## Verified Code Facts

- Harness distribution is `study-agent-harness` v0.2.0 and Cardine distribution
  is `cardine` v0.2.0.
- Both currently install the same regular top-level package `study_agent`, so
  side-by-side wheels collide.
- Cardine adds product tutor, Luna, UI/auth/settings, continuation/handoff, and
  diagnostics modules, while lacking multiple Harness KB v0.2 modules.
- Existing parity tests are intra-tree, not cross-distribution install/parity
  tests.
- `LocalRepository` is the current composition seam in both projects.
- Both share event/blob/run/retrieval repository layout; Cardine also stores tutor
  continuation/handoff operational data in `runs.sqlite3`.

## Remaining Decision Frontier

The decision frontier is empty. Package Foundation, Cardine Adoption, Harness
Future Runtime, and Cardine Future Product have no remaining user-level design
decisions. The only remaining grilling action is explicit user confirmation of
the shared-understanding summary before materializing specs and beads.

## Approved Harness Future Runtime Contracts

- One outer Job lifecycle replaces parallel worker/lesson lifecycle ownership:
  `QUEUED -> RUNNING -> SUSPENDED | SUCCEEDED | FAILED | CANCELLED | STALE`.
  Lease is RUNNING metadata; retry creates a new attempt under the same Job;
  playbook checkpoints remain subordinate execution proofs.
- Job/lease/heartbeat/attempt/queue data is durable operational state in a
  separate JobStore. Only a domain owner can commit a canonical outcome.
- Workflow identity derives from capability/version, authority scope,
  idempotency key, and input fingerprints; child jobs derive from parent,
  position, and task fingerprint; attempts are monotonic. Same identity with
  different bytes conflicts.
- Defaults: 60s lease; 20s heartbeat; expired lease requeues with increasing
  fencing token; global and per-workflow concurrency 8; hierarchy depth 1;
  maximum 64 child jobs; FIFO deterministic claims; at-least-once execution and
  exactly-once canonical commit through owner idempotency.
- Retry defaults: maximum 3 attempts; 1s/2s/4s exponential backoff with +/-20%
  jitter and 30s cap; only timeout/rate-limit/provider-5xx/declared-transient
  failures retry. Validation, authorization, integrity, conflict, and stale do
  not. Cancellation completes at safe points without canonical rollback.
  Suspended jobs hold no lease; resume tokens bind job/attempt/checkpoint/
  authority/input/dependencies and conflicting response bytes fail.
- Decision Trace is a separate append-only stream with trace/workflow/job/
  attempt/capability, correlation/causation, transition, validators/outcomes,
  safe error, fingerprints, and timestamps. It excludes full prompts, excerpts,
  outputs, secrets, raw personal identity, and chain-of-thought. Minimal trace
  lasts until repository deletion; redacted diagnostic payloads last 14 days;
  optional OpenTelemetry loss never changes execution.
- Flashcard planner/coordinator/leaf/reviewer/assembler run as Jobs. Each leaf
  sees one evidence cluster and produces at most 6 candidates under a declared
  context budget. Partial proposals require visible missing clusters/failures;
  no silent omission or automatic acceptance. Reducers inspect candidates,
  rubrics, fingerprints, coverage, and references, fetching source spans only
  for targeted conflicts. Specialized lifecycle stores are removed after parity.
- WebEvidencePort is provider-neutral; scripted offline connector is mandatory;
  first optional live adapter is OpenAI Responses web_search; no arbitrary
  direct URL fetch in v1 and no live adapter in base core.
- Web defaults: at most 8 queries/workflow, 10 candidates/query, 45s timeout,
  256 KiB extracted text/candidate, HTTPS references only, no cookies/
  credentials/active execution, untrusted connector output, 7-day candidate
  retention, and explicit partial result on network failure.
- Broker cannot admit evidence. HUMAN or injected trusted SERVICE admits an
  exact snapshot; receipt records hash, URL, timestamp, connector, query,
  provenance, policy/version, and decision. Admitted content becomes immutable
  Source Revision; synthesis never becomes a primary source.
- Harness owns portable ReferenceExamRef, ExamProfile, GenerationPlan,
  SyntheticVerification, and CoverageReport lifecycle schemas with opaque host
  academic refs. Sealed means application authority, not claimed encryption.
  Student sees an accepted plan and progressive questions only during attempt;
  answers after finalization. Lists/search/export/trace/errors never leak sealed
  content.
- Verification lifecycle: approved profile + accepted plan -> generation Jobs
  -> independent coverage reviewer -> deterministic release gate ->
  presentation. Generator cannot self-review/release; any required missing,
  partial, or uncertain coverage blocks release.
- Novelty: normalized exact match regenerates; 5-token-shingle Jaccard >=0.75
  regenerates; 0.55-0.75 is uncertain and regenerates; two failed regenerations
  suspend without exposing content to the learner.
- Every generated question pins profile, plan, sources, scope/objective refs,
  prompt/worker/validator versions. Drift stales only affected shards;
  regeneration creates a new revision and reruns global review; prior attempts
  remain historical. Harness returns presentation receipt; Cardine owns attempt,
  response, grade, and contest.
- Offline gates: 100% schema/authority/citation/sealed-leak checks; 100% required
  coverage; zero unsupported claims; reviewer macro-F1 >=0.95; deterministic
  replay equality. Live opt-in candidates compare with an exact Luna baseline;
  critical capability promotion requires no critical failures and quality
  within 3 percentage points. Cost/token/latency are reported separately.
- Release waves: Job+Trace -> Flashcard Jobs -> Web Evidence -> Sealed
  Verification -> Eval/package release.

### Closed Cardine Future Product decision checklist

1. Curriculum concept/objective IDs, revisions, and activation.
2. Graph relation vocabulary, acyclicity, propagation, and objective axis.
3. Alignment admission and syllabus backbone/conflict behavior.
4. Educational Authority/Currency/Integrity contracts and official-syllabus
   discovery.
5. Conversation cardinality and Study Session linkage.
6. Assistance Context and Evaluative Turn exact fields/preconditions.
7. Reference Exam/Question identity and Exam Profile composition/activation.
8. Synthetic verification integration, criteria, authenticity, prior exposure,
   and grade-contest effects.
9. Versioned deterministic Evidence Strength policy and golden vectors.
10. Mastery scale, temporal model, contradictions, and graph propagation.
11. Readiness aggregation, coverage/confidence, critical-gap thresholds.
12. Estimate rebuild/cache keys and explanation contract.
13. Substantial artifact revision classification and RetentionObservation types.
14. Study Plan aggregate and deterministic NextActivity algorithm.
15. Provider consent, secret blocking, retention/export/delete policy.
16. UI truth contract, sealed-content leak prevention, deterministic vs Luna
   responsibilities, and product eval gates.
17. Final dependency ordering between product lanes.

## Approved Cardine Curriculum, Tutoring, and Exam Contracts

- ConceptId and LearningObjectiveId are opaque, course-scoped, text-independent
  IDs created by an injected ID factory. Curriculum revisions are immutable;
  one revision is active per course; activation requires authorized HUMAN or
  injected SERVICE decision and never rewrites historical evidence.
- Curriculum relation vocabulary v1 is closed: `IS_PART_OF` is an acyclic
  multi-parent hierarchy; `REQUIRES` is independently acyclic prerequisite;
  `RELATED_TO` is symmetric and non-propagating. Only IS_PART_OF may contribute
  to attenuated roll-ups. Objectives are course-scoped/versioned on a separate
  axis; alignments pin revision, concept, and objective.
- Curriculum activation requires an approved official syllabus. Sources/exams
  may propose nodes/relations but cannot remove syllabus requirements. All v1
  generated alignments require HUMAN approval; confidence/provenance alone
  grants no authority; unresolved conflict blocks activation.
- EducationalAuthority values: OFFICIAL_SYLLABUS, LECTURER_MATERIAL,
  REFERENCE_TEXT, LEARNER_NOTE, ADMITTED_WEB, OTHER. SourceCurrency values:
  CURRENT, PARTIAL_MATCH, OUT_OF_PERIOD, UNKNOWN, derived deterministically
  from academic period, lecturer, and syllabus. SourceIntegrity is separate:
  VERIFIED, FAILED, UNKNOWN.
- Syllabus discovery is user-triggered through WebEvidenceBroker; candidates
  remain quarantined until learner admission; no periodic search or automatic
  replacement.
- One durable Conversation per course in v1 spans many bounded StudySessions.
  Sessions record intent/activity/start/end/outcome. Browser/auth sessions are
  unrelated. Model context uses a bound

[truncated]
```

## Search Results

### `Harness`

exit_code: `0`

```text
week/README.md:25:816fa20b1c370e7cc18133bc2ede126a0ff1339deae337ba3f8c32b1deb834c6  Study Agent Harness - Voiceover Jerry B.mp3
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-elevenlabs-under-3m.txt:14:Study Agent Harness is the missing layer: <break time="0.4s" /> an open-source execution core that keeps an AI tutor persistent, <break time="0.2s" /> source-grounded, <break time="0.2s" /> and replayable. <break time="0.6s" />
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-full-2m18.txt:3:Matches: output/Study Agent Harness - Launch Video.mp4  (138 s)
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-full-2m18.txt:13:[00:06–00:16]  Title reveal — "Study Agent Harness" / "Persistent · Source-grounded · Replayable"
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-full-2m18.txt:14:Study Agent Harness is the missing layer: / an open-source execution core that keeps
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-full-2m18.txt:18:[00:16–00:29]  Architecture — "Model proposes · Harness executes"
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-captions-final.srt:48:Study Agent Harness.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/build-week-voiceover-elevenlabs.txt:27:Study Agent Harness is the missing layer: <break time="0.4s" /> an open-source execution core that keeps an AI tutor persistent, <break time="0.2s" /> source-grounded, <break time="0.2s" /> and replayable. <break time="1.0s" />
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/proof/flywheel-data.json:4:    "title": "OSS Harness v0.1 Immutable Text Ingestion"
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/proof/index.html:7:    <title>Study Agent Harness — Build Week launch film</title>
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/proof/index.html:14:        <a class="wordmark" href="https://github.com/EbrahimAbdelwahed/study-agent-harness">Study Agent Harness</a>
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/proof/index.html:139:        <p class="eyebrow">Study Agent Harness</p>
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/tasks/20260712-oss-harness-v01-batch7/typed-tools-reference-harness.md:26:- Implement StudyHarness as an async lifecycle-event adapter over GroundingAskService.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/logs/2026-08-09-2315--harness--package-foundation-spec-materialization--log.md:1:# Log: Harness Package Foundation spec materialization
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/logs/2026-08-09-2315--harness--package-foundation-spec-materialization--log.md:5:Area: Study Agent Harness package boundary
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/logs/2026-08-09-2315--harness--package-foundation-spec-materialization--log.md:9:Materialized the approved Harness Package Foundation specification as one
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/docs/archive/build-week/proof/flywheel-index.html:61:              <strong data-bind="feature_title">OSS Harness v0.1 Immutable Text Ingestion</strong>
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1927--harness--package-and-runtime-specs--plan.md:1:# Plan: Harness package and future runtime specs
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1927--harness--package-and-runtime-specs--plan.md:4:Area: Study Agent Harness
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1927--harness--package-and-runtime-specs--plan.md:9:as independently verifiable slices that preserve the Harness context boundary.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-01-1030--knowledge-base--kb13-e2e-integration--plan.md:9:Study Agent Harness branch, then expose an offline, typed evidence API that
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-02-1135--tools--selective-public-tool-surface--plan.md:8:Expose the active Harness's canonical course, ingestion, session, artifact,
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-02-1254--release--oss-release-candidate--plan.md:8:Prepare the contemporary Study Agent Harness core as an installable, honest,
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-02-1200--repository--build-week-archive-and-worktree-consolidation--plan.md:8:Leave the Study Agent Harness primary checkout as the sole worktree, retain the
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/src/study_agent/operator_skill/SKILL.md:3:description: Operate a local Study Agent Harness repository through its machine-readable CLI contract. Use when an agent must discover, initialize, populate, verify, use, retry, recover, or export a provider-neutral event-sourced study repository.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/src/study_agent/operator_skill/SKILL.md:6:# Operate Study Agent Harness
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:1:# Harness Future Runtime Features
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:7:Owning repository: Study Agent Harness
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:11:Add the provider-neutral runtime waves approved in the Cardine/Harness handoff:
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:21:Harness owns Job/lease/attempt/retry mechanics, executor checkpoints,
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:23:schemas, validation, replay, and trust boundaries. Harness does not own
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:76:a Harness source, import, package, schema, or test dependency. HR slices must
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:77:continue to name only released Harness contracts and generic ports.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:127:Run the narrow slice command first, then from the Harness root:
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:163:You are implementing the Harness Future Runtime Features spec. Start with
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-12-eval-release.md:26:- Add release report/eval fixtures under `tests/evals/` and package scripts only in Harness-owned release configuration.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-10-sealed-contracts.md:38:resolved by the injected host port and never enters Harness events, traces,
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-01-contract-firewall.md:47:Harness Package Foundation 0.3.0 and its curated API/error/authority seams.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-01-contract-firewall.md:73:An overly broad contract can smuggle Cardine policy into Harness or permit
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CHANGELOG.md:3:Notable public changes are recorded here. Study Agent Harness is alpha
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT.md:1:# Study Agent Harness Context
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT.md:11:- **Harness** — the provider-neutral, local-first execution layer. It owns
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:10:from study_agent.application import StudyHarness
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:117:    harness: StudyHarness, question: str, execution_context: object
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:130:    harness = StudyHarness(service)
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:161:    harness = StudyHarness(service)
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:189:    harness = StudyHarness(service)
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:252:    harness = StudyHarness(service)
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_tool_harness_parity.py:285:    harness = StudyHarness(cast(GroundingAskService, ExplodingGrounding()))
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_reference_cli_release.py:13:from study_agent.application import StudyHarness
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_reference_cli_release.py:141:    harness: StudyHarness, question: str, context: ExecutionContext
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/tests/integration/test_reference_cli_release.py:311:            _events(StudyHarness(service), "brachial plexus", parity_context)
```

### `Cardine`

exit_code: `0`

```text
/slices/PF-09-distribution.md:11:only; PF-09 does not import or test the Cardine repository.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:15:- No Cardine package changes, source migration, CLI alias shim, or product
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:16:  entry-point implementation. Actual Cardine co-install/parity is not a PF-09
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:26:  package remains exclusively `study_agent`. Cardine owns `cardine` and must
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:39:  or entry-point collision. Actual Cardine co-install success belongs only to
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:40:  CA-04 and CA-10; no Harness test imports Cardine.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:48:- The adoption release recommendation is `0.3.0`; Cardine pins the exact
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:63:  fixture distributions; neither fixture is a Cardine source dependency.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:77:Do not add a Harness-side workaround for the copied Cardine namespace. Remove
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:79:Cardine adoption owns removal of its duplicate package and aliases.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:103:must not resolve a sibling checkout or import Cardine. Actual Cardine
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-09-distribution.md:113:  only; Cardine migration owns product alias removal.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-04-storage-contract-kit.md:15:  or Cardine-owned storage layout.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-04-storage-contract-kit.md:40:  not add a second transaction authority. Cardine owns physical paths and
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:7:of Cardine academic policy. Existing replayable proposal, grading, evidence,
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:12:- No Cardine artifact kinds, curriculum alignment, mastery, readiness, study
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:32:  references; Cardine owns artifact-kind semantics and product effects.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:50:  idempotency, stale-sequence, cancellation, and safe-failure rules. Cardine
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:103:of Learner Model or Cardine imports.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-07-artifacts-assessments-recall.md:118:  subfacades with no Cardine/product types.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/slices/PF-01-public-manifest.md:14:- No Cardine import, product DTO, auth surface, or copied source mirror.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/worker-briefs/PF-03-events-upcasting-module.md:38:  metadata, CLI/UI, Cardine, workers, telemetry, or new dependencies
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT-MAP.md:23:  Cardine[Future Cardine consumer\nversioned package]
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT-MAP.md:35:  Runtime -. package boundary .-> Cardine
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/CONTEXT-MAP.md:80:- Publish a versioned package for downstream consumers such as Cardine; do not
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/worker-briefs/PF-02-failures-authority.md:36:  `pyproject.toml`, CLI/UI, Cardine, credentials, or new dependencies
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/package-foundation/worker-briefs/PF-01-public-manifest.md:39:- `pyproject.toml`, domain behavior, adapters, CLI, UI, Cardine, or optional
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:11:Add the provider-neutral runtime waves approved in the Cardine/Harness handoff:
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:15:Cardine. Cardine receives only released portable contracts and presentation
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:137:3.13 environment. The wheel must contain no Cardine references, no required
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/README.md:166:offline checks. Do not add Cardine policy, a second lifecycle owner, live
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-12-eval-release.md:9:No automatic model promotion, mandatory credentials/network, cost-based quality substitution, Cardine release, distributed JobStore, or new runtime behavior.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-12-eval-release.md:41:Review report schema, threshold vectors, artifact contents, import/entry-point manifest, no-Cardine scan, no-secret scan, and CI matrix on Python 3.12/3.13.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-12-eval-release.md:69:contain no Cardine references or mandatory provider dependency.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-04-decision-trace.md:44:future slice may promote either into a Cardine/product projection.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-05-lifecycle-convergence.md:12:No new worker capability, web evidence, sealed assessment, Cardine adapter, or
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-10-sealed-contracts.md:9:No Cardine authenticity/profile approval, attempt/grade/contest, generation worker, network connector, encryption claim, or learner-model input.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-06-flashcard-planning.md:13:Cardine curriculum alignment, learner model, or automatic omission of failed
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-06-flashcard-planning.md:65:limits or carry Cardine policy.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-08-web-evidence-core.md:9:No live network in the base package, arbitrary URL fetch, cookies, credentials, active-page execution, automatic admission, source replacement, or Cardine syllabus policy.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-02-job-store.md:12:Decision Trace, canonical domain-event writes, distributed queue, or Cardine
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-01-contract-firewall.md:13:Cardine import, curriculum/mastery/readiness/planning field, or learner-facing
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-01-contract-firewall.md:60:list. Confirm no module imports Cardine or product application code.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-01-contract-firewall.md:73:An overly broad contract can smuggle Cardine policy into Harness or permit
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-07-flashcard-jobs.md:9:No Cardine artifact kinds or approval policy, learner estimates, trace payloads in artifact exports, or self-reviewing generator.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/specs/future-runtime/slices/HR-11-sealed-workflow.md:5:Run approved profile and accepted plan through generation Jobs, independent coverage review, deterministic release, and progressive presentation. Return only a presentation receipt to Cardine; Cardine owns attempts, responses, criteria, grades, and contests.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/logs/2026-08-09-2315--harness--package-foundation-spec-materialization--log.md:42:  sealed verification, Decision Trace, Cardine product policy, or mandatory
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1927--harness--package-and-runtime-specs--plan.md:15:- Out of scope: implementation code, Cardine product policy, publishing.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1927--harness--package-and-runtime-specs--plan.md:27:- Release gates depending on Cardine code rather than portable fixtures.
/Users/ebrahimabdelwahed/Desktop/Med/Lezioni/Audio_to_Sbobina/.worktrees/study-agent-harness-integration/dev/plans/2026-08-09-1722--integration--foundation-main--plan.md:24:    observability, evals, or Cardine package consumption;
```


## Orchestrator Notes

- Convert rough requirements into explicit acceptance criteria before implementation.
- Keep generated worker scopes narrow and file-bounded.
- Use `br`/`bv` as durable task graph once beads are approved.
