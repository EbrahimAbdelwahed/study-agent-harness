# Integrating an agent host

Study Agent Harness exposes a process boundary and a low-level Python tool
boundary. Both delegate to the same canonical application owners.

## Choose a boundary

Use the installed `study-agent` command when process isolation, language
neutrality, or shell orchestration is useful. Begin with:

```bash
study-agent --json describe
```

The response is the source of truth for available commands and tools, their
effects, required context, retry guidance, contract versions, and unavailable
capabilities. Do not copy that inventory into agent prompts or integration code.

Use `study_agent.tools` for an in-process Python host. The public module provides
immutable contracts, manifests, schema validation, owner composition, and
`StudyToolRegistry`. A host should keep its composition code thin:

```python
from study_agent.domain import ExecutionContext
from study_agent.tools import StudyToolRegistry


async def invoke_from_host(
    registry: StudyToolRegistry,
    name: str,
    arguments: dict[str, object],
    context: ExecutionContext,
):
    return await registry.invoke(name, arguments, context)
```

The host obtains the registry from its own trusted composition root. The
repository composition used by the
[external-agent example](examples/external_agent.py) is a reference, not a
stable general-purpose SDK facade.

## Keep authority outside model arguments

The host, not the model, selects the principal, capabilities, repository,
course, session, correlation identity, and idempotency identity. Model-proposed
arguments are validated against closed schemas and cannot grant authority or
choose providers, prompts, policies, or runtime pins.

Compose `AgentOperationOwners` only from the contemporary canonical services.
Do not reproduce course, ingestion, session, artifact, assessment, retrieval,
or knowledge business logic in the integration layer.

## Retry and verification

Inspect each manifest's effect and idempotency contract before invoking it. For
canonical writes, preserve host-supplied identities across lost output. Treat a
retryable conflict as a request to refresh canonical state and follow the
reported retry contract, not as permission to invent a new operation.

Use the CLI's verification guidance or read the owner-backed result after a
mutation. Error codes are closed and safe to expose; internal exception text is
not part of the public contract.

## Current limits

This is an alpha integration surface. The package does not promise a stable
top-level client facade, hosted authentication, multi-tenancy, a browser shell,
or automatic provider selection. Recall scheduling remains unavailable until a
contemporary canonical owner is integrated and verified.

Importing the core does not initialize a repository, read credentials, contact
a provider, or require an optional model SDK.
