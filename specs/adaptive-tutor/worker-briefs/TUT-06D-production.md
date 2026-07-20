# Worker Brief: TUT-06D optional OpenAI Responses adapter

## Assignment

Implement only TUT-06D after reading the accepted bead, TUT-06A/B contracts,
the current plan, and current official OpenAI Responses/Python SDK contracts.

## Allowed Files

- `pyproject.toml`: add only an `openai` optional dependency extra.
- `src/study_agent/adapters/host/__init__.py`.
- `src/study_agent/adapters/host/openai_responses.py`.
- `src/study_agent/ports/tutor_host.py`: relocate the existing retryable
  decision-provider error to the neutral port boundary only.
- `src/study_agent/ports/__init__.py`: additive error re-export only.
- `src/study_agent/hosts/contracts.py`: add the provider-neutral strict
  `decision_schema(context)` builder.
- `src/study_agent/hosts/runner.py`: import/re-export that same error; no runner
  behavior change.
- `src/study_agent/hosts/__init__.py`: additive schema/error public exports.
- `tests/unit/adapters/host/test_openai_responses.py`.
- `tests/contract/hosts/test_openai_decision_adapter.py`.
- `tests/unit/hosts/test_tutor_host_contracts.py`: decision-schema contract only.
- `tests/integration/test_openai_responses_host_smoke.py`.
- `tests/architecture/test_tutor_host_boundaries.py`: additive import firewall.

No other file may change.

## Exact Contract

- Add exactly `openai = ["openai>=2.46,<3"]` as the optional extra.
- `OpenAIResponsesTutorConfig`: frozen/slotted, explicit bounded `model_id`,
  `api_key_env`, positive bounded timeout, and positive bounded
  `max_output_tokens`. It stores no key and has no retry count. Reject secret-looking env
  values, path/control/provider-selector injection, subscription/OAuth/cookie
  modes, and unknown configuration.
- Trusted composition resolves the named environment variable only when
  constructing a live client. The key is never retained in a public dataclass,
  repr, receipt, exception, request fixture, or invocation provenance.
- `OpenAIResponsesTutorDecisionPort` implements exactly
  `TutorDecisionPort.decide(context, interruption)`. Permit an injected narrow
  async Responses client protocol for offline fixtures. Lazy-load `openai` only
  in the default client factory; importing any core/public module without the
  optional SDK succeeds.
- One request contains only a versioned constant host instruction,
  `context.to_json()` as untrusted/redacted input, and
  `hosts.contracts.decision_schema(context)`. Because strict Responses
  Structured Outputs requires a root object, the schema root is exactly
  `{type: object, properties: {decision: {anyOf: [...] }},
  required: [decision], additionalProperties: false}`. The inner variants are
  exact branches for ask/message/stop, context-advertised start
  capabilities with their exact input schemas, and answer-dialogue only when an
  exact pending descriptor exists. It permits no provider/authority/path/hidden
  field and uses `additionalProperties=false` throughout. The adapter must not
  build or alter this schema. The adapter unwraps only `decision`, serializes it
  canonically, and delegates to `decision_from_bytes`. Set no provider tool, previous
  response id, conversation, store, background, include, metadata, or file
  search. Set `store=False`, `max_output_tokens=config.max_output_tokens`, and
  do not send local file bytes in D.
- Use current Responses structured output shape under `text.format`; accept only
  `status="completed"`, no `error`/`incomplete_details`, no refusal/tool/function
  output, and exactly one assistant message yielding one bounded non-empty
  `output_text`; reasoning items may coexist. Parse canonical
  JSON and call existing `decision_from_bytes(..., context)`/validation. Unknown
  capabilities, authority fields, paths, hidden fields, or invalid decisions
  fail closed before returning.
- Default SDK client uses an owned `AsyncOpenAI(api_key=..., timeout=...,
  max_retries=0)` and closes it after the request. Injected clients are not
  closed by the adapter. Map only documented connection, timeout, 408/409/429/5xx
  classes/statuses to `RetryableTutorDecisionError`; auth, bad request,
  refusal/incomplete/malformed responses fail with one safe non-retryable typed
  adapter error. Never include provider body, headers, request id, key, context,
  or decision in error text/repr.
- Move `RetryableTutorDecisionError` from `hosts.runner` to
  `ports.tutor_host`, with runner import/re-export compatibility. This is the
  only neutral-boundary change; the adapter must not import runner internals.
- Interruption before/after client construction and request returns a safe
  non-retryable interruption error with no later effects. The adapter does not
  cancel provider work or claim cancellation support in v0.2.
- No gateway, ExecutionContext, source/file service, ingestion, event/store,
  tool registry, prompt registry, or model-specific pedagogy import.

## Tests

- Exact request snapshot and decision schema; valid decision parity with the
  scripted adapter.
- Missing SDK/key, unsupported subscription modes, secret redaction.
- Retry classification and runner budget ownership (`max_retries=0`).
- Malformed/refused/incomplete/multiple/oversized/authority-injected output.
- Interruption before/after request; no extra effect.
- Base import firewall; opt-in live smoke requires SDK + named key + explicit
  model and otherwise skips.

## Stop Conditions

Stop if implementation needs Agents SDK, provider tools/files, gateway changes,
new TutorDecision variants, a default model id, provider-managed state, or any
file outside the allowlist.
