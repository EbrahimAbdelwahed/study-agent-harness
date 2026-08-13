# PF-02 — Failures and authority

## Outcome

The facade exposes one closed error taxonomy and one host-supplied authority
context. Malformed input, stale state, missing resources, conflicts,
unauthorized calls, unavailable adapters, and unexpected failures are safe,
typed, and distinguishable; provider, SQLite, and filesystem exceptions never
cross the public boundary.

## Non-goals

- No product authorization policy, browser session, cookie, credential, or
  multi-user sharing model.
- No model approval path, automatic principal creation, or environment-based
  authority discovery.
- No retry scheduler or Job lifecycle; retry metadata is only part of a safe
  failure value and idempotent command contract.

## Exact contracts

- Public failures are `HarnessError` subclasses with this closed taxonomy:
  `ValidationFailure`, `StaleFailure`, `UnauthorizedFailure`,
  `ConflictFailure`, `NotFoundFailure`, `UnavailableDependencyFailure`, and
  `InternalFailure`.
- Every failure carries `code`, `message`, `retryable`, `correlation_id`, and
  safe structured `details`. Messages and details never contain credentials,
  cookies, raw prompts, chain-of-thought, or arbitrary adapter tracebacks.
  Unknown exceptions map to `InternalFailure` and retain the original exception
  only as a local `__cause__`.
- `PrincipalKind` is exactly `HUMAN`, `SERVICE`, or `MODEL`. `Principal`,
  `Grant`, `Scope`, and `AuthorityContext` are opaque, immutable, read-only
  values with no public constructor, deserializer, copy, or pickle path.
  `HostAuthority.issue(...)` exists only at the host composition root and
  returns a context bound to that issuer by a private process-local
  object-capability marker. A distinct injected `AuthorityPort` owns
  `require(...)` and `require_durable(...)`; it rejects contexts issued by a
  different host before checking claims. The port exposes no issuance method,
  and providers receive neither issuer nor port. No global, environment value,
  credential, random token, persistent token, or cryptographic identity is
  used.
- `HostAuthority.issue(...)` accepts collections of complete grant/scope
  strings only. Scalar `str`/`bytes` values fail closed instead of being
  iterated into character claims.
- `MODEL` authority is read/propose-only. It cannot approve, append a durable
  command, grant itself scope, or select identity, parentage, policy, or
  canonical outcome. Cookies and browser credentials never enter the context.
- Every durable command carries an `IdempotencyKey` and canonical input
  fingerprint. Same key plus same command kind and bytes returns the original
  result; same key plus different kind or bytes raises `ConflictFailure`.
  A new command with stale stream position raises `StaleFailure` without
  mutation. Cancellation before append returns a typed cancellation outcome;
  committed events are not rolled back.
- The facade maps existing internal error codes and adapter exceptions into the
  seven public classes through one explicit exhaustive `ErrorCode` table.
  Import-time coverage and an all-enum test fail when a legacy code is added
  without a public mapping. Internal messages and details never cross this
  boundary; unknown exceptions retain only a local `__cause__`.
- Public error sanitization is fail-closed and bounded: maximum depth 8,
  256 visited nodes, 64 items per container, 1,024 UTF-8 bytes per string, and
  16 KiB for serialized details. Cycles, unsupported values, non-string keys,
  non-finite numbers, and exceeded bounds become fixed safe sentinels without
  calling arbitrary `repr` or `str`. A sensitive key or sensitive marker
  anywhere in free text—including `Basic`, `Bearer`, and recognized API-key
  shapes under neutral keys—redacts the whole value. JSON serialization uses
  `allow_nan=False` and a bounded final fallback.
- Equivalent model protocol failures map to one public category regardless of
  whether they arrive as `ModelError(PROTOCOL_ERROR)` or legacy
  `StudyError(MODEL_PROTOCOL_ERROR)`.
- Authority checks happen before schema validation of durable effects and
  before adapter calls, so unauthorized or model-originated requests cannot
  probe persistence or providers.

## Probable files

- `src/study_agent/api/authority.py` — facade exports and authority value types.
- `src/study_agent/domain/errors.py` — internal-to-public failure mapping.
- `src/study_agent/domain/authority.py` or `src/study_agent/ports/authority.py`
  — principal, grant, scope, and idempotency values.
- `src/study_agent/application/errors.py` — adapter exception translation.
- `tests/contract/test_public_failures.py` and
  `tests/contract/test_authority_context.py` — taxonomy and authority gates.
- `tests/architecture/test_authority_boundaries.py` — model/provider import and
  write-path checks.

## Dependencies

PF-01 supplies the facade and manifest. PF-03, PF-04, PF-06, PF-07, and PF-08
consume these failures and authority values.

## Removal conditions

Remove any temporary public aliases for legacy error classes before accepting
the slice. Internal adapters may retain private exception types only when the
facade maps every path to the closed taxonomy.

## Review surface

Review the actor/grant/scope issuance path, cross-issuer rejection, model
rejection cases, safe bounded error serialization, and idempotency fingerprint
inputs. Verify that authority checks cannot be bypassed by direct construction,
`dataclasses.replace`, assignment, serialization, direct adapter calls, or a
replayed provider response. Arbitrary reflection and `object.__new__` are
outside the supported API threat model.

## Exact verification

```text
uv run --python 3.13 --extra dev pytest -q tests/contract/test_public_failures.py tests/contract/test_authority_context.py tests/architecture/test_authority_boundaries.py
uv run --python 3.13 --extra dev pytest -q tests/integration/test_event_state_kernel.py tests/integration/test_capability_gateway_lifecycle.py
uv run --python 3.13 --extra dev ruff check src/study_agent/api src/study_agent/domain src/study_agent/application tests/contract tests/architecture
git diff --check
```

The focused tests must cover all seven classes, every legacy error enum value,
adapter exception translation, direct/replace/cross-issuer authority forgery,
MODEL rejection with maximal claims, equal-key convergence, changed-input
conflict, stale no-op, multi-token credentials, nested/query/header secrets,
cycles, excessive depth/size, non-finite values, and strict JSON decoding.

## Risks

- Existing error enums are broader than the public taxonomy. Keep the mapping
  explicit instead of leaking or silently collapsing useful public categories.
- Principal values can accidentally become transport DTOs. Keep credentials and
  browser/session secrets outside the value types.
- Hashing mutable or unordered inputs can break retries. Canonicalize and freeze
  command inputs before computing identity.

## Definition of done

- All public failures inherit one facade-visible base and use the closed set.
- Host-supplied authority rejects model writes before any durable or provider
  operation.
- Idempotency semantics and cooperative cancellation are covered by tests.
- No provider, SQLite, filesystem, or traceback type leaks through public APIs.
- Focused tests and lint pass on the declared command set.
