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
is reported honestly as unavailable until a contemporary canonical owner is
integrated and verified.

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
