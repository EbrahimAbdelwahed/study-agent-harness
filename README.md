# Study Agent Harness

`study-agent-harness` is an alpha Python library and reference CLI for
source-grounded study procedures. It is designed as an OSS core that can sit
behind different agents, models, providers, and product interfaces without
making any of them canonical.

The approved v0.1 contract lives in
[`docs/specs/oss-study-agent-harness-v0-1.md`](docs/specs/oss-study-agent-harness-v0-1.md).
The reference CLI and export boundary are specified separately in
[`docs/specs/oss-harness-v0-1-reference-cli-and-export.md`](docs/specs/oss-harness-v0-1-reference-cli-and-export.md).
The durable scope and architecture rationale are recorded in
[`docs/decisions/`](docs/decisions/). Contributor and vulnerability-reporting
guidance live in [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`SECURITY.md`](SECURITY.md).

## Architecture

The append-only domain event stream is canonical state. Course, source, and
session projections are read models: they may be rebuilt from events and must
not acquire independent authority. SQLite run checkpoints, the lexical index,
local configuration, and filesystem layout are operational state. They support
recovery and performance, but they do not redefine the study record.

Versioned skills describe study capabilities and playbooks compose their
behaviour. Model adapters remain technical transport translators. They do not
own prompts, study policy, authority, or domain state. An embedding host creates
trusted execution context separately from model-proposed arguments; the
[`external agent example`](docs/examples/external_agent.py) shows this boundary
without coupling it to an agent SDK.

The reference CLI is another composition adapter over the same application
services. It is not a second behaviour layer.

## Install and first local workflow

Python 3.12 or newer is required. The runtime uses only the standard library.
From a checkout:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/study-agent --help
```

Start with an offline repository, create a course, and add local UTF-8 text or
Markdown sources:

```bash
study-agent init ./my-study-repository
study-agent --repository ./my-study-repository course create \
  --title "Example course" --learning-goal "Explain the core concepts"
study-agent --repository ./my-study-repository source add COURSE_ID notes.md
```

The create response supplies `COURSE_ID`. Continue with `source list`, `ask`,
the explicit session commands, `export`, or `doctor`; `study-agent --help` and
the command-level help are the source of truth for their current arguments.
Use the global `--json` option for one machine-clean success or safe error
document on stdout.

The default repository is offline and has no model configured. Retrieval,
replay, export, and `doctor` remain credential-free; `ask` requires an explicitly
configured model adapter.

## Models and credentials

The bundled network adapter speaks an OpenAI-compatible HTTP protocol. Its
configuration records technical values such as endpoint URL, model identifier,
timeout, and the **name** of a credential environment variable. The credential
value itself is read from the environment when the repository is opened and is
never written to repository configuration.

Any service that implements that compatible protocol may be used. DeepSeek is
therefore an optional endpoint for inexpensive experiments, not a core
dependency or a privileged provider. Other transports belong behind their own
generic adapters while the domain, skills, playbooks, and CLI remain unchanged.

Use `study-agent init --help` for the adapter-setting syntax. Never put an API
key in a model setting, committed file, command transcript, or export.

## Recovery and interruption semantics

Source ingestion commits the canonical source revision before rebuilding the
discardable retrieval index. If indexing fails, the CLI reports that the source
was committed and treats rebuilding as a recoverable operational failure; it
does not roll back or conceal the event. `doctor` verifies event replay and
retrieval rebuildability without contacting a provider.

The current OpenAI-compatible model call has no in-flight cancellation
primitive. A pre-run interruption produces no mutation. Once an automatic
session ask has entered its durable operation, SIGINT is deferred until the
authoritative outcome is emitted; the harness never invents a canonical
`cancelled` transition for work it could not actually cancel. Hosts that need
responsive cancellation must supply a real adapter/engine cancellation
transition rather than interpreting process interruption as domain state.

## Portable export

Export v1 is a deterministic, credential-free view of canonical course state.
Repeated exports at the same event high-water mark are byte-identical. The
allowlisted bundle excludes credentials, credential-variable names, endpoints,
provider request/response bodies, run checkpoints, host paths, blob references,
and source bytes. Its checksummed manifest is the integrity boundary; the
canonical event stream remains the recovery boundary.

## Development and release gates

Install the development extras and run the offline quality gates:

```bash
python3.12 -m pip install -e '.[dev]'
python3.12 -m pytest
python3.12 -m ruff check .
python3.12 -m mypy
```

Release acceptance also requires deterministic replay/export checks, the
credential-free end-to-end CLI fixture, a clean wheel install and CLI smoke on
Python 3.12, and independent semantic review. Network smoke tests are opt-in;
the default suite must not require an API key, provider SDK, or hosted service.

## Project status

Version 0.1.0 is an alpha release and its public API is not stable. The project
is available under the [Apache License 2.0](LICENSE).
