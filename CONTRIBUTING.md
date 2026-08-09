# Contributing

The repository is preparing for public contributions to the provider-neutral
harness, its reference adapters, tests, and documentation. Product features,
hosted-platform concerns, and provider-specific study behaviour are outside its
scope.

Unless explicitly stated otherwise, contributions intentionally submitted for
inclusion in this project are licensed under the
[Apache License 2.0](LICENSE), without additional terms or conditions.

## Development setup

Python 3.12 or newer is required.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Before submitting a change, run:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
```

Keep changes small and preserve these architectural boundaries:

- canonical study state comes from the append-only domain event stream;
- projections, indexes, and run checkpoints do not become authorities;
- skills and playbooks own study behaviour;
- model/provider adapters translate technical protocols only;
- trusted execution context is separate from model-proposed tool arguments;
- tests are offline by default and never require credentials.

Add behaviour-focused tests for contract changes. Document durable architectural
decisions under `docs/decisions/` and update affected specs. Never commit local
study repositories, source material, exports, credentials, raw provider
payloads, or raw Flywheel execution artifacts.

For release-facing changes, follow the
[`source release candidate checklist`](docs/maintainer/release-checklist.md) and
record exact verification rather than claiming publication or support that has
not been approved.
