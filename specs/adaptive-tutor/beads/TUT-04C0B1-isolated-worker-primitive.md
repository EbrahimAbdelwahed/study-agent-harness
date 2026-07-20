# Task Bead: TUT-04C0B1 isolated generation worker primitive

Status: Done
Priority: P0
Type: expand
Depends On: TUT-03

## Worker Profile

Reuse `grounded-study-artifact-worker`; require an `architecture-auditor` before
implementation because this changes a shared execution boundary.

## Outcome

A generic provider-neutral primitive executes one complete allowlisted child
capability/playbook run in a fresh execution context and returns a strict receipt
without exposing worker scratch context to its caller.

## Acceptance Criteria

- [ ] Strict `GenerationWorkerTask` and `GenerationWorkerReceipt` contracts bind
  task identity, task kind, prompt/skill/playbook/model pins, allowlisted JSON
  payload fingerprint, output schema/fingerprint, validators, and run identity.
- [ ] The payload admits only explicit task data, bounded canonical continuation
  summary, language/preferences, trusted evidence/index references, and output
  schema. Tutor message history, unrelated raw materials, sibling drafts,
  credentials, principal identifiers, provider selection, and canonical artifact
  authority are rejected.
- [ ] Execution creates a fresh child run context and delegates exactly once to
  the existing capability gateway/playbook engine. The profile playbook's
  `ModelStep` is the sole model effect; B1 never constructs or invokes a second
  `ModelRequest`. No prior ModelMessage list or hidden agent memory is supplied.
- [ ] A provider adapter may internally use a native subagent feature, but no
  provider SDK, agent type, or model name enters core task/receipt contracts.
- [ ] Structured-output fallback, cancellation, failure, retry, and validator
  provenance remain compatible with the existing playbook engine. Exact retry
  observes the persisted receipt rather than repeating a completed model effect.
- [ ] The wrapper may start/resume one named existing capability through an
  injected gateway port, but cannot bypass skill/playbook behavior, dispatch a
  model directly, or mutate the capability manifest.
- [ ] The caller receives a compact status/receipt by default; detailed verified
  output is available through a typed run view. Raw reasoning and malformed
  attempts are not copied into tutor context or canonical state.
- [ ] Exact codecs, fingerprints, secret rejection, portability, and old
  playbook/capability behavior remain green; no StudyTool is added.

## Likely Files / Packages

- a narrow generic worker package under `src/study_agent/workers/` or an audited
  equivalent
- minimal playbook runtime changes only if required by the accepted design
- focused unit, recovery, portability, and architecture tests

## Out of Scope

- Lesson planning/fan-out, profile prompts, artifact commit, hosted queues, UI,
  provider adapters, arbitrary agent loops/memory, and `sbobby-web`.

## Verification

- Allowlisted task, forbidden history/secret/provider fields, fresh request,
  fallback, cancel, malformed output, exact retry, process restart, receipt
  tamper, typed detail view, Ruff, strict mypy, architecture/tool parity, full
  offline gates.

## Grilling Evidence

ADR-0010 requires semantic subagent isolation without a provider-specific
subagent API. This primitive is deliberately generic so flashcard and exam
workers share the same boundary.
