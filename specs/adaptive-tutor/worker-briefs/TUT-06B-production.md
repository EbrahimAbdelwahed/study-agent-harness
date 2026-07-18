# Worker Brief: TUT-06B bounded scripted tutor loop

## Assignment

Implement `TUT-06B` from
`specs/adaptive-tutor/beads/TUT-06B-bounded-scripted-tutor-loop.md` as the first
serialized phase of Batch A. Do not begin TUT-06C.

## Worker Profile

Reuse `docs/worker-profiles/reference-tutor-host-worker.md`.

## Read First

- `AGENTS.md`
- `dev/plans/2026-07-18-1145--adaptive-tutor--tut06-batch-a--plan.md`
- `docs/decisions/ADR-0004--adaptive-tutor-host-boundary.md`
- `specs/adaptive-tutor/beads/TUT-06A-provider-neutral-tutor-host-contracts.md`
- `specs/adaptive-tutor/beads/TUT-06B-bounded-scripted-tutor-loop.md`
- `src/study_agent/hosts/contracts.py`
- `src/study_agent/hosts/context.py`
- `src/study_agent/ports/tutor_host.py`
- `src/study_agent/capabilities/contracts.py`
- `src/study_agent/capabilities/gateway.py`
- `tests/unit/hosts/test_tutor_host_contracts.py`
- `tests/integration/test_capability_gateway_lifecycle.py`
- `tests/architecture/test_tutor_host_boundaries.py`

## Allowed Files

You may change:

- `src/study_agent/capabilities/contracts.py`: add only the exact suspended
  dialogue `response_schema` public field and validation/freeze.
- `src/study_agent/capabilities/gateway.py`: populate that schema from the
  already-selected `DialogueStep`; no new lookup API.
- `src/study_agent/capabilities/__init__.py`: export compatibility only if needed.
- `src/study_agent/hosts/runner.py`: new runner contracts and implementation.
- `src/study_agent/hosts/scripted.py`: deterministic scripted decision adapter.
- `src/study_agent/hosts/__init__.py`: explicit public exports.
- `src/study_agent/ports/tutor_runner.py`: new narrow gateway, authority,
  action-identity, and continuation-store protocols.
- `src/study_agent/ports/__init__.py`: explicit public exports.
- `tests/unit/hosts/test_tutor_host_runner.py`: limits, codecs, mapping, scripted
  adapter, interruption and redaction.
- `tests/integration/test_tutor_host_runner.py`: public gateway recordings,
  suspension/resume, retry, stale refresh and process-loss ports.
- `tests/architecture/test_tutor_host_boundaries.py`: additive import/API gates.
- existing capability contract/gateway tests only where the new
  `response_schema` field changes their exact constructors/assertions.

Do not change:

- TUT-06C files, source input, ingestion, filesystem adapters, domain/state,
  skills/playbooks/prompts, capability manifests/bindings, tutor snapshot,
  learner evidence, artifacts/assessments/recall, StudyTools, CLI, dependencies,
  docs/specs, `sbobby-web`, or unrelated tests.

## Required Public Contract

### Capability suspension correction

- `SuspendedCapabilityOutcome` gains `response_schema: JsonObject` before its
  default status field.
- Freeze and validate it as the exact `DialogueStep.response_schema.value`.
- The gateway constructs it from the selected public dialogue step. The runner
  must never inspect gateway bindings, engine checkpoints, or playbooks to
  obtain the schema.
- Update all exact constructor/golden tests. Do not change manifest fingerprints,
  continuation fingerprints, run ids, or existing outcome status values.

### Runner ports

Define narrow protocols in `ports/tutor_runner.py` with no implementation or
provider imports:

- `TutorCapabilityGatewayPort`: `discover`, async `start`, async `resume` with
  the same public signatures/outcomes as `StudyCapabilityGateway`.
- `TutorHostAuthorityPort`: creates the trusted `ExecutionContext` for a new
  start from course/session/capability plus host action identity; model inputs
  are never authority inputs.
- `TutorHostActionIdentityPort`: returns a stable `HostActionIdentity` for the
  exact `(host_turn_id, context_fingerprint, decision_fingerprint,
  decision_generation)` and
  must return a distinct identity for changed committed fields.
- `TutorContinuationStore`: create/load/delete one strict host-only record keyed
  by course/session plus opaque continuation fingerprint. The record contains
  exact `CapabilityContinuation`, its original trusted `ExecutionContext`, and
  the model-visible `PendingContinuationDescriptor`. Identical create is
  idempotent; changed bytes conflict.

Keep `ports/tutor_host.py` unchanged: its exact two-protocol surface is already
pinned by architecture tests.

### Runner values

Implement strict frozen values in `hosts/runner.py`:

- `TutorHostLimits(max_decisions, max_provider_attempts_per_decision,
  max_stale_refreshes, max_emitted_text_chars)`; all fields are positive ints.
- A closed `TutorHostRunStatus` covering: `completed`, `suspended`,
  `terminated`, `cancelled`, `failed`, `in_progress`, `needs_learner_input`,
  `assistant_message`, `stopped`, `interrupted`, `budget_exhausted`.
- One strict `TutorHostRunResult` with status, optional `HostRetryReceipt`,
  optional bounded learner-facing text, optional frozen completed output, and
  optional `PendingContinuationDescriptor`. Enforce a status/field matrix:
  completed alone may expose output; suspended alone requires pending;
  question/message alone require text; interrupted may retain an already-issued
  pending descriptor but never output; every other non-success has no output.
- A typed retryable decision-provider error. Retry only that error, up to the
  provider-attempt limit; do not catch `BaseException` or silently retry schema,
  programming, cancellation, or gateway errors.
- Canonical JSON/fingerprint only where state crosses the continuation-store or
  a public receipt boundary. Do not create a generic serialization framework.

### Runner algorithm

For `TutorHostRunner.run(course_id, session_id, host_turn_id,
interruption, *, retry_receipt=None, pending_fingerprint=None)`:

1. Validate the trusted opaque `host_turn_id` and check interruption.
2. If `pending_fingerprint` is present, load exactly that continuation for the
   same course/session and project its descriptor. If absent, project no pending
   descriptor; the store has no implicit current/list operation. Assemble a
   fresh `TutorHostContext` from snapshot reader, learner-evidence reader, the
   same gateway discovery port, and that selected descriptor.
3. Call `TutorDecisionPort.decide` with provider-attempt accounting; check
   interruption immediately before and after each call.
4. Validate the returned decision against that exact context before issuing an
   action identity or gateway effect.
5. Enforce decision and emitted-text budgets before effects/return.
6. For ask/message/stop, return the corresponding typed result without gateway
   calls.
7. For start, obtain action identity bound to host turn/context/decision/
   generation and trusted `ExecutionContext` out of band, create
   `HostRetryReceipt`, then call only `gateway.start`.
8. For answer-dialogue, load the exact host-only continuation record by the
   selected descriptor fingerprint. Issue a new action identity/receipt bound to
   the answer decision; exact answer retry reuses it. Call only `gateway.resume`
   with the continuation's original stored trusted `ExecutionContext`, so its
   authority/idempotency remain unchanged. Delete the record only after a
   non-suspended, non-IN_PROGRESS exact result. The decision never carries
   continuation bytes/context.
9. Check interruption before and after every gateway/store effect. If an effect
   completed before interruption, return `interrupted` and never expose its
   completed output. A newly suspended continuation must already be stored and
   may be returned only as its descriptor.
10. Map completed/suspended/terminated/cancelled/failed one-to-one.
    `CapabilityGatewayError(IN_PROGRESS, retryable=True)` becomes the distinct
    host `in_progress` result and preserves the same action identity for retry.
    Other gateway errors become fail-closed host `failed` results with bounded
    generic text; no exception repr, authority, ids, or inputs leak.
11. On stale: invalidate any stale pending continuation, increment the stale
    budget, reassemble both views, call the decision adapter again, and require
    a new decision generation/action identity. Never replay the stale decision
    or continuation. Exhaustion returns `budget_exhausted` without output.
12. With `retry_receipt`, require the same host turn, context fingerprint,
    decision/action fingerprint and stable action identity before gateway
    invocation, then increment `attempt`. Any mismatch is a fail-closed result
    with zero gateway calls. Without a receipt, two identical decisions in two
    different host turns must receive distinct action identities.

The runner owns no canonical events, projection, pedagogy, capability registry,
model call, provider branch, or ambient persistence.

## Scripted Adapter

- Accept an immutable ordered tuple of exact expected context fingerprints and
  decisions/results.
- Each call consumes exactly one entry and fails closed on context mismatch,
  extra call, interruption, or exhaustion.
- No environment, time, filesystem, network, random, gateway, or state-owner
  access.
- Repr/errors must not include context bodies, inputs, credentials, or trusted
  authority.

## Acceptance Matrix

Tests must independently cover:

- direct completion and exact output;
- start -> suspend -> persisted descriptor -> learner answer -> resume complete;
- exact start and resume lost-output retries with one gateway execution;
- receipt mismatch for turn/context/decision/action fails before gateway, and
  identical decisions in distinct host turns do not collide;
- changed decision under reused host identity rejected before gateway;
- retryable IN_PROGRESS remains distinct and uses the same action identity;
- stale start and stale resume refresh both views and require a second scripted
  decision/new identity;
- completed, suspended, terminated, cancelled, stale, failed and every
  non-IN_PROGRESS gateway error;
- positive limit validation, decision exhaustion, provider-attempt exhaustion,
  stale exhaustion and text exhaustion;
- interruption before/after assemble, decide, identity, authority, store,
  start/resume, and result mapping; assert zero later effects;
- no raw continuation, execution context, principal, grants, retry identity,
  provider/model configuration, prompt/trace, or hidden answer in model-facing
  context/result/errors;
- runner/service reconstruction over the same continuation-store bytes.
- explicit pending fingerprint selection: absent, exact present, missing,
  forged, cross-course and cross-session.

Use `asyncio.run`; do not add `pytest-asyncio`.

## Verification

Run:

```bash
PYTHONPATH=.:src .venv/bin/python -m pytest -q tests/unit/hosts/test_tutor_host_contracts.py tests/unit/hosts/test_tutor_host_runner.py tests/integration/test_tutor_host_runner.py tests/integration/test_capability_gateway_lifecycle.py tests/architecture/test_tutor_host_boundaries.py
.venv/bin/ruff check src/study_agent/hosts src/study_agent/ports/tutor_runner.py src/study_agent/capabilities/contracts.py src/study_agent/capabilities/gateway.py tests/unit/hosts/test_tutor_host_runner.py tests/integration/test_tutor_host_runner.py tests/architecture/test_tutor_host_boundaries.py
MYPYPATH=src .venv/bin/mypy --strict src/study_agent/hosts src/study_agent/ports/tutor_runner.py src/study_agent/capabilities/contracts.py src/study_agent/capabilities/gateway.py tests/unit/hosts/test_tutor_host_runner.py tests/integration/test_tutor_host_runner.py
git diff --check
```

## Stop Conditions

Stop and report instead of deciding if implementation requires:

- another capability outcome/status change beyond suspended response schema;
- a new decision kind, StudyTool, capability manifest, skill/playbook, event,
  dependency, persistence technology, provider SDK, or model-facing authority;
- inspection of private gateway bindings/playbooks;
- changes outside the allowed files.

## Report Back

Return files changed, exact public API change, algorithm/acceptance coverage,
verification results, forbidden-boundary confirmation, and unresolved items. Do
not commit, update status, start TUT-06C, or delegate.
