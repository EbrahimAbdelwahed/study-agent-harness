# OSS Harness v0.1: Reference CLI and deterministic export

Status: Implemented; Python 3.12 install smoke pending CI
Date: 2026-07-12

Implementation review: [`../reviews/20260712-oss-harness-v01-batch8.md`](../reviews/20260712-oss-harness-v01-batch8.md)

## Goal

Ship the small stdlib reference CLI required by v0.1 without creating a second behavior layer: canonical mutations remain application-service commands over the event log, `ask` uses the same `GroundingAskService`, and export is a deterministic credential-free view of canonical state.

## Problem

The approved core and typed tools are not yet a usable distribution. Existing test-only run storage cannot recover across CLI processes, no production composition root exists, and no allowlisted export contract prevents credentials or operational traces from leaking. Wiring commands directly now would create a demo path that violates the release's persistence and portability claims.

## In Scope

- Durable SQLite `RunStore`, UTC system clock, and read-only course/session enumeration needed by a process-restart-safe CLI.
- Strict non-secret local repository configuration and composition root.
- `study-agent init`, `course create`, `source add/list`, `ask`, `session list/resume`, `export`, and `doctor`, including machine-clean `--json` output.
- Deterministic export v1 and offline end-to-end fixtures.

## Out of Scope

- Import, deletion, hosted auth, MCP/HTTP/Tau, provider-specific domain behavior, generic agent loops, token streaming, product/UI work, PDF/audio, or `sbobby-web`.

## Architectural decisions

1. The CLI is a composition adapter. It calls host-authority application services directly for create/ingest/lifecycle/export and the existing `GroundingAskService` for `ask`; it does not turn host operations into model tools.
2. The core remains model/provider agnostic. Configuration selects an adapter capability; OpenAI-compatible endpoint/model/key-env values remain operational and credentials are resolved from the environment only.
3. The local layout is operational, never canonical truth: `study-agent.json`, `state/events.sqlite3`, `state/runs.sqlite3`, `state/retrieval.sqlite3`, `blobs/`, and `exports/`.
4. An omitted ask session creates a new host-generated session. A supplied session must be active. `session resume` requires both course and session identity; there is no hidden global current-session pointer.
5. Source identity is explicit when supplied and otherwise derived deterministically by the host from the normalized repository-relative path. Metadata defaults are documented and overridable; content changes create revisions under the same source identity.
6. Canonical source ingestion commits before discardable index rebuild. Index failure is reported as a recoverable operational failure and never rolls back or conceals the committed source event.
7. Export v1 is a directory containing canonical JSON/JSONL files for the course, source manifests, sessions, answers, and events plus a checksummed manifest. Ordering and encoding are canonical; no timestamp, host path, provider request/response, endpoint, environment-variable name, checkpoint, blob reference, source bytes, or credential is exported.
8. `doctor` is offline by default and reports layout/config, SQLite/FTS5, event decode/projection replay, retrieval rebuildability, and run-store schema without printing secret values.
9. JSON mode writes exactly one success document or one stable safe error document to stdout. Progress and diagnostics use stderr and cannot corrupt JSON. Empty lists and insufficient evidence are successful outcomes.
10. Cancellation is honest: pre-run interruption produces no mutation; once a run exists, only a real engine/service cancellation transition may be reported. v0.1 must not fabricate a canonical cancelled record when the current adapter cannot cancel in flight.

## Implementation wavefront

1. `cli-persistence-prerequisites`: SQLite CAS RunStore, SystemClock, deterministic course/session listing ports and conformance tests.
2. `local-repository-composition`: strict config/layout, provider-neutral engine factory, local composition, safe model adapter registry.
3. `deterministic-export`: application export contract, exact decoder, atomic filesystem writer, redaction/determinism tests.
4. `reference-cli-commands`: parser/output/errors and init/course/source/session commands.
5. `reference-cli-ask-release`: ask/export/doctor wiring, fake-model end-to-end, packaging entry point and manual fixture.

## Acceptance Criteria

- Process restart preserves playbook run create/load/CAS/recovery semantics.
- CLI code never writes canonical SQLite/projection tables directly.
- The identical ask service/tool/playbook owns direct, harness, tool, and CLI behavior.
- Two identical exports of unchanged state are byte-identical and contain no credential/config/operational trace material.
- `--json` output is stable and machine-clean; failure exit codes and safe envelopes are covered.
- An offline temporary repository completes init, course creation, two source ingestions, retrieval, deterministic fake-model ask, suspend/resume, export, and doctor.
- Installed `study-agent --help` works in a clean Python 3.12 environment.
- Full pytest, Ruff, mypy, architecture, replay, and independent semantic review gates pass.

## Verification

- Focused contract/unit tests per bead, then `.venv/bin/python -m pytest`.
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy`
- clean Python 3.12 wheel/install/CLI smoke.
- manual offline medical-text CLI walkthrough and export inspection.
