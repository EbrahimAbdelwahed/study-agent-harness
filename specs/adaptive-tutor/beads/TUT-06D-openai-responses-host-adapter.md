# Task Bead: TUT-06D optional OpenAI Responses host adapter

Status: Blocked on TUT-06B and TUT-06C
Priority: P0
Type: adapter
Depends On: TUT-06B, TUT-06C

## Required Preflight

Capture and review current official OpenAI documentation for the Responses API,
structured tool/function outputs, interruption/cancellation, file inputs, SDK
installation, authentication, errors, retries, and currently supported model
identifiers. If those contracts materially contradict this bead, stop for a
spec/ADR update before production edits.

## Provisional Architecture Decision

Implement a direct Responses decision adapter, not an Agents SDK host. The
harness already owns the bounded loop, gateway, authority, lifecycle, retries,
and traces. An SDK-owned agent loop would duplicate those owners. This decision
is provisional until the required official-documentation preflight completes.

## Outcome

One optional API-key OpenAI Responses adapter translates the exact redacted
provider-neutral host context and decision schema without invoking capabilities,
filesystems, ingestion, event stores, or any other study effect.

## Acceptance Criteria

- [ ] Add one optional `openai` dependency extra; the base distribution retains
  zero runtime dependencies. Core, scripted host, CLI offline paths, and public
  imports succeed when the SDK is absent.
- [ ] All `openai` imports are lazy or confined to the optional technical host
  adapter package. No Agents SDK import or agent-owned loop/state is added.
- [ ] Configuration requires an explicit model id and API-key environment
  variable name plus bounded timeout/retry settings. The key is resolved only
  by trusted composition, is excluded from repr/errors/receipts, and is never
  persisted or passed through model decisions.
- [ ] The model id is configurable and recorded only as sanitized technical
  invocation provenance. No model name changes study behavior, capability
  schemas, prompts, gateway authority, or host limits.
- [ ] One Responses request contains only the versioned host instruction,
  redacted `TutorHostContext`, advertised decision schema, and already-approved
  host-file inputs. The adapter returns only a validated `TutorDecision`.
- [ ] The adapter cannot call gateway start/resume, create execution context,
  assign grants/idempotency, ingest files, or write canonical/operational host
  state beyond its bounded technical invocation receipt.
- [ ] Provider errors map to closed safe adapter errors. Only documented
  transient classes are retryable, retries remain within the runner's provider
  attempt budget, and secret/provider response bodies never enter public
  outcomes.
- [ ] API-key mode is the only supported live integration. ChatGPT subscription,
  browser/session cookie reuse, OAuth impersonation, or subscription-to-API
  equivalence returns explicit unsupported configuration and is documented as
  unavailable.
- [ ] Request/response fixtures prove provider output cannot inject authority,
  hidden fields, unknown capabilities, path/secret fields, or alternate tool
  execution. An opt-in live smoke uses an explicitly configured documented
  model and is skipped without the SDK/key/configuration.

## Verification

- Optional-extra clean installs; import firewall; SDK transport fixtures;
  decision-adapter conformance shared with scripted adapter; secret/error/retry
  tests; opt-in Responses smoke; Ruff; strict mypy.
