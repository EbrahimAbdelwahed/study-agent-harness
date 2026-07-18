# Reference tutor host

The reference composition is an offline proof of the public adaptive-tutor
boundary. It is intentionally not a product UI or a second workflow engine:
the `TutorHostRunner` remains the only bounded decision loop and the existing
capability gateway remains the only canonical study-effect owner.

Run it from a checkout with no provider setup:

```bash
PYTHONPATH=src .venv/bin/python examples/reference_tutor_host.py
```

The example accepts free-form learner context, discovers the public capability
manifest, executes a direct completion, suspends for one clarification, resumes
from the exact persisted continuation descriptor after an evidence refresh,
and captures one trusted Markdown snapshot. The scripted adapter and the
recorded Responses fixture use the same runner, gateway, authority, action
identity, and continuation-store seam. Their status trace is:

```text
completed -> suspended -> completed
```

## Optional OpenAI Responses adapter

The core distribution has zero runtime dependencies. Install the technical
adapter only when it is needed:

```bash
.venv/bin/pip install -e '.[openai]'
```

Composition must provide an explicit model id and the name of an environment
variable containing an API key:

```python
OpenAIResponsesTutorConfig(
    model_id="gpt-5.6",
    api_key_env="OPENAI_API_KEY",
)
```

The key is read only while constructing the live SDK client; it is not stored in
configuration, host receipts, prompts, errors, or exports. Requests use the
redacted `TutorHostContext`, a closed context-derived JSON schema, bounded
`max_output_tokens`, `store=False`, and SDK `max_retries=0`. The runner owns
provider retry budgets, stale refresh, interruption handling, and all capability
effects. The adapter does not use tools, files, previous response ids,
conversation state, streaming, or background mode.

The adapter is API-key-only. A ChatGPT subscription, browser cookie, OAuth
session, or account login is not API authority and is not supported. Network
calls and provider billing occur only when a trusted composition explicitly
chooses the optional adapter and invokes it; the default example and test suite
never contact a provider. Do not send raw source bytes, hidden answers,
credentials, paths, grants, or execution context to a model.

## Trusted host responsibilities

The embedding host owns course/session authority, action identity, retry
receipts, and interruption tokens. It may capture `.txt` or `.md` through the
`HostFileRegistry`, which reads each path once beneath its trusted source
adapter, stores a bounded canonical snapshot, and exposes only an opaque
descriptor to the model. Lookup returns explicitly marked untrusted bytes only
to trusted host code. Ingestion requires a separate host-supplied command with
source id, title, trust, role, sequence, and execution context; model output
cannot choose any of those fields.

Continuation descriptors are opaque and owner-bound. A retry must present the
same host turn, context, decision, and action fingerprints. Stale state is
refreshed and re-decided rather than replayed. Failed, interrupted, malformed,
terminated, cancelled, or budget-exhausted work is fail-closed and cannot be
reported as a completed capability or append an unauthorized canonical event.
