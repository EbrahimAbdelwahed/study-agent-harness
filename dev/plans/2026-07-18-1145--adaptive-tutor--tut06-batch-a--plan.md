# Plan: TUT-06 Batch A — bounded host runner and file snapshots

Date: 2026-07-18 11:45
Area: adaptive-tutor
Status: Completed 2026-07-18

## Goal

Implement TUT-06B and TUT-06C as two serialized, independently green tracer
bullets. The result is a provider-neutral scripted tutor loop and a trusted,
immutable local text/Markdown snapshot boundary ready for the later OpenAI
adapter. No provider SDK, UI, CLI, or product workflow enters this batch.

## Scope

- In scope:
  - bounded host-runner contracts, outcome mapping, action identity/retry,
    interruption, stale refresh, and scripted decision adapter;
  - gateway-facing and trusted-authority ports that expose only the minimum
    existing capability lifecycle;
  - host-owned snapshot contracts, capture service, operational store/registry,
    descriptor projection, trusted byte lookup, and ingestion bridge;
  - offline unit, contract, integration, architecture, tamper, restart, and
    filesystem-race coverage;
  - status, worker brief, log, and handoff updates.
- Out of scope:
  - OpenAI/DeepSeek/provider imports or network calls;
  - PDF, OCR, audio, vector retrieval, auth, subscriptions, UI, CLI, hosted
    persistence, file watching, arbitrary paths, or automatic role/trust policy;
  - new StudyTools, capability manifests, skills/playbooks, canonical events,
    tutor-snapshot fields, learner-evidence fields, or `sbobby-web`;
  - repository-wide mypy backlog unrelated to the changed files.

## Approach

1. TUT-06B: add a pure provider-neutral runner over TUT-06A contracts.
   - Reuse `TutorHostContextAssembler`, `TutorDecisionPort`,
     `HostActionIdentity`, `HostRetryReceipt`, decision validation, and the
     existing gateway outcome union.
   - Introduce only narrow gateway/authority/action-identity seams required to
     keep trusted values out of model-visible decisions.
   - Persist no canonical or operational state in the runner. Exact retry is
     expressed through host-supplied identity and deterministic receipts.
   - Map every gateway outcome one-to-one; never collapse suspended, stale,
     cancelled, terminated, failed, completed, or in-progress.
   - Reassemble both sequence-consistent views after stale and request a fresh
     decision/action identity; never reuse a stale continuation.
   - Extend `SuspendedCapabilityOutcome` with the exact frozen public dialogue
     `response_schema` already owned by its `DialogueStep`. This is the only
     capability public-API change in Batch A; the runner must not inspect
     bindings or playbooks to reconstruct the schema.
   - Treat retryable `CapabilityGatewayError(IN_PROGRESS)` as a distinct typed
     host outcome. Do not add an `IN_PROGRESS` capability outcome or change the
     gateway's existing public lifecycle contract.
   - Store the exact continuation and its trusted execution context behind an
     injected operational continuation-store port. Only the opaque descriptor
     enters `TutorHostContext`; stale invalidates the stored generation.
   - Bind each runner invocation to a trusted opaque `host_turn_id` and optional
     prior `HostRetryReceipt`. Exact lost-output retry must match turn, context,
     decision, and action fingerprints before any gateway effect; two otherwise
     identical turns remain distinct.
   - Select pending continuation explicitly by optional opaque fingerprint on
     the runner call. The continuation store exposes exact keyed lookup only; it
     has no implicit current/listing policy.
2. Verify TUT-06B narrowly before starting TUT-06C.
3. TUT-06C: add a separate trusted-host file-snapshot boundary.
   - Reuse `SourceInputPort`/`FilesystemSourceInput`; never copy filesystem race
     logic into the host package.
   - Capture exact bytes once, validate strict UTF-8 and existing bounds, bind
     them to opaque id + course + session + checksum, and store canonical bytes
     in a caller-owned operational store.
   - Project only `HostFileDescriptor` into `TutorHostContext`. Paths and bytes
     are structurally absent.
   - Require exact owner/checksum lookup before returning untrusted content or
     constructing an ingestion command. The bridge receives trusted source id,
     title, role/trust authorization, sequence, and execution context out of
     band; model decisions cannot supply them.
   - Fail closed on changed, missing, expired, forged, cross-owner, duplicate-
     identity conflict, oversized, malformed, or path-injected inputs before
     decision-provider or ingestion effects.
   - TUT-06C does not add file ingestion or source-role variants to the closed
     `TutorDecision` union. Capture, descriptor projection, and lookup are
     model-visible only through existing context. Ingestion is an explicit
     trusted-host bridge call whose source id/title/trust/role/sequence/context
     arguments are all supplied out of band.
4. Run one semantic review over the combined production diff and one focused
   security/architecture audit of the file/authority boundary. Apply only
   approved findings.
5. Run combined TUT-06A/B/C tests, architecture gates, source Ruff/mypy, full
   offline pytest, build, diff check, then update statuses/log/handoff.

## Risks

- Public runner outcomes can accidentally create a second capability lifecycle
  or hide gateway distinctions.
- Retry identity can become model-mintable or change across stale refresh.
- Snapshot contracts can leak paths/bytes or accidentally become canonical
  course state.
- A convenience ingestion bridge can allow model-selected authority, source
  identity, trust, role, or expected sequence.
- Expiry semantics can introduce wall-clock nondeterminism. The implementation
  must use `ClockPort`; snapshot capture records `captured_at` plus an explicit
  positive TTL from trusted configuration and derives `expires_at`. No direct
  ambient time read is allowed in contracts/services.
- Adding protocols to `ports/tutor_host.py` would break its exact narrow-port
  architecture test; new runner/file ports should live in dedicated modules.
- Host file ids are supplied by a trusted injected identity port. Exact retry
  must return the same id for the same course/session/checksum declaration and
  a different id when bytes change; the decision adapter cannot supply it.
- Configured snapshot count cannot exceed `MAX_HOST_FILES`; configured aggregate
  bytes cannot exceed `MAX_TOTAL_SOURCE_BYTES`. The v0.1 in-memory implementation
  has the fixed destination `src/study_agent/adapters/memory/host_file.py`.

## Verification

- `PYTHONPATH=.:src .venv/bin/python -m pytest -q tests/unit/hosts tests/contract/hosts tests/integration/test_tutor_host_runner.py tests/integration/test_host_file_snapshots.py tests/architecture/test_tutor_host_boundaries.py tests/contract/filesystem/test_source_input.py tests/contract/ports/test_source_input_contract.py`
- `.venv/bin/ruff check <changed production and test files>`
- `MYPYPATH=src .venv/bin/mypy --strict <changed production and test files>`
- `PYTHONPATH=.:src .venv/bin/python -m pytest -q`
- `.venv/bin/ruff check src tests`
- `MYPYPATH=src .venv/bin/mypy --strict src`
- `uv build`
- `git diff --check`

## Review Economy

- No subagent review for local wiring or documentation.
- One Luna implementer owns production plus focused tests for each serialized
  phase under this plan.
- One combined semantic reviewer runs after both phases.
- One architecture/security audit is limited to public contracts, authority,
  snapshot storage, path/byte redaction, and ingestion effects.
- Independent test work is added only if the combined reviewer identifies an
  uncovered behavioral boundary; do not duplicate the implementer's fixtures by
  default.

## Completion

- TUT-06B and TUT-06C are implemented and marked Done.
- One aggregated semantic/security review found four P1, five P2, and one P3
  surface issue; all were fixed and the targeted re-review returned APPROVE.
- Final gates: 1612 tests passed, 2 expected skips; Ruff clean; strict mypy
  clean on 222 source files; `uv build` produced sdist and wheel; diff check
  clean.
