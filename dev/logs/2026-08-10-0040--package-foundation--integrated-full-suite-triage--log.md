# Log: Integrated full-suite triage

Date: 2026-08-10 00:40 CEST
Area: package foundation / PF-10 adoption release gate
Bead: `study-agent-harness-integration-1u7`
HEAD: `206cd9a` (`chore: dispatch PF-05 and PF-06 review fixes`)

## Scope and coordination

This lane followed `docs/worker-briefs/20260809-harness-package-foundation/pf-10.md`
and the PF-10 release slice. The Beads item was inspected before editing and
remains `IN_PROGRESS`; it was not closed. `dev/index.md` is not present in this
checkout. The relevant handoff, integration plan/log, PF-10 worker brief, and
PF-10 spec/slice were read.

The mandated Agent Mail start command succeeded far enough to identify
`MistyPine` and the project, but the required inbox read returned HTTP 404 from
`http://127.0.0.1:8765/mcp/`; no inbox contents were available. The semantic
follow-up bead created from this triage is:

`study-agent-harness-integration-1u7.1` — Fix PF-06 capability contract
regressions found by integrated full-suite triage.

Only this log is changed by the lane. No `src/`, `tests/`, `specs/`,
`docs/worker-briefs/`, `pyproject.toml`, or `uv.lock` file was modified.

## Verification environment

The worktree initially had no `.venv/bin/python`, so the four mandated
commands were first attempted exactly as written. The three Python commands
returned exit 127 (`zsh:1: no such file or directory: .venv/bin/python`);
`git diff --check` passed. The ignored worktree environment was then created
with `uv sync --offline --extra dev` from the existing lockfile and the exact
commands were rerun. Versions were Python 3.13.12, pytest 9.1.1, Ruff 0.16.2,
and mypy 2.3.0.

## Exact required command outcomes

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **FAIL** — 2,428 passed, 9 failed, 15 skipped in 35.23s; exit 1 |
| `.venv/bin/python -m ruff check .` | **PASS** — `All checks passed!` |
| `.venv/bin/python -m mypy` | **FAIL** — 39 errors in 16 files; checked 571 source files; exit 1 |
| `git diff --check` | **PASS** |

The 15 skips are the documented optional or environment-gated cases: one
Unix-socket filesystem test, one PDF-containment test, two opt-in live-model
tests, one optional FSRS integration test, two distribution-artifact tests
(artifacts were not built in this triage), and eight optional FSRS unit cases.

## Pytest failures and classification

The eight capability failures below are semantic/contract failures and are
covered by child bead `study-agent-harness-integration-1u7.1`.

1. `tests/architecture/test_artifact_contract_boundaries.py::test_exact_seven_tools_and_two_ordinary_gateway_capabilities_are_unchanged`
2. `tests/architecture/test_artifact_lifecycle_boundaries.py::test_exact_two_events_seven_tools_and_two_tutor_capabilities_are_unchanged`

Both snapshot checks observe fingerprint drift. Current values are:

```text
assess_understanding  5a0926ba3370f98e779bd8893dc4c0e74b7d2f0d8736f5ceb2629f7f22cef00f
explain_concept       6152fa654f94e1e09c513aa153e873230b51815da749c377ad1d2caeab2ea1c4
```

The snapshots expect, respectively,
`d49d55b2efa04f642fbd08e84204b50f471422335d01dc283bfa26da4753b1d9` and
`6e563b5a2750f8077f3a516ea50a7e938552824afbde7bbebed04563783465c3`.
The minimal reproduction is either node above.

3. `tests/contract/events/test_kernel_module.py::test_kernel_module_rejects_noncanonical_typed_capability_id[study:read]`
4. `tests/contract/events/test_kernel_module.py::test_kernel_module_rejects_noncanonical_typed_capability_id[study/read]`
5. `tests/contract/events/test_kernel_module.py::test_kernel_module_rejects_noncanonical_typed_capability_id[study_agent.read]`
6. `tests/contract/events/test_kernel_module.py::test_kernel_module_rejects_noncanonical_typed_capability_id[study-agent.read]`

Each test expects `ValidationFailure` from `KernelModule`, but the helper
constructs `CapabilityId` first and `src/study_agent/capabilities/contracts.py:54`
raises `ValueError: capability id must use one canonical dot namespace` before
the kernel is reached.

7. `tests/contract/test_public_capabilities_facade.py::test_facade_exports_only_provider_neutral_capability_contracts`

`TerminatedCapabilityOutcome` exists in the contracts module and is returned by
the gateway recovery path, but `src/study_agent/api/capabilities.py` no longer
exposes it; the minimal reproduction is `getattr(facade,
"TerminatedCapabilityOutcome")`, which raises `AttributeError`.

8. `tests/unit/capabilities/test_flashcard_dispatch.py::test_resume_rejects_tampered_receipt_pins_definition_authority_and_generation`

The first `dataclasses.replace` tampering the continuation inputs raises
`ValueError: continuation input_fingerprint is inconsistent with inputs` in
`src/study_agent/capabilities/contracts.py:412`, before
`dispatcher.resume(...)` can return the expected `CapabilityGatewayError`.

The remaining failure is environment-only:

9. `tests/integration/demo/TUT08/test_browser_surface.py::test_local_browser_journey_serves_page_state_and_free_form_entry`

The normal sandbox run fails at `socket.bind` with
`PermissionError: [Errno 1] Operation not permitted`. Rerunning exactly this
node with local socket binding permitted passed: `1 passed in 0.72s`. This is
not a product failure.

The eight semantic nodes were rerun together as a focused reproduction and
returned `8 failed in 0.37s` with the same causes.

## Mypy failure inventory

The mypy gate is independently red under the lockfile toolchain (39 errors,
16 files). Errors cover source/test typing around capability-ID unions and the
excluded terminated outcome, source citation test helper typing and stale
`type: ignore` comments, the public dynamic facade assertion, and one missing
annotation in `tests/architecture/test_tool_registry_boundaries.py`. The exact
reported files/locations are:

```text
tests/contract/test_public_sources_facade.py:44
tests/unit/knowledge/test_citation_v2.py:240
tests/contract/sources/test_source_revision_contract.py:33,71-74
tests/contract/sources/test_citation_contract.py:143,182,195
src/study_agent/assessments/verified_grading.py:244
src/study_agent/exams/analysis.py:173
src/study_agent/capabilities/gateway.py:136,450
tests/unit/capabilities/test_gateway_worker_adapter.py:164,422
tests/unit/capabilities/test_flashcard_dispatch.py:770
src/study_agent/capabilities/morphology_flashcards.py:261
src/study_agent/capabilities/hybrid_flashcards.py:270
tests/contract/test_public_capabilities_facade.py:61
tests/unit/capabilities/test_morphology_flashcards.py:59
tests/unit/capabilities/test_hybrid_flashcards.py:39
tests/architecture/test_tool_registry_boundaries.py:81
tests/integration/test_headless_artifact_flow.py:574
```

These typing failures were reported but not changed in this reporting-only
lane. They remain a release-gate risk in addition to the semantic child bead.

## Residual risks

- PF-10 is not green on integrated HEAD: the full offline suite and strict
  mypy gate fail.
- The capability contract follow-up must resolve whether fingerprint changes
  are intended contract updates or regressions, then restore constructor,
  facade, and continuation tamper behavior without weakening canonical-state
  validation.
- Inbox state could not be read because the Agent Mail MCP endpoint returned
  HTTP 404. Completion notification is therefore sent as the next explicit
  coordination action.
- Browser and Unix-socket skips/failures remain host-sandbox constraints; the
  browser node was proven to pass with the required capability.
