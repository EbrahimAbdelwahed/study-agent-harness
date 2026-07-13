# Feature Spec: OSS Study-Agent Harness v0.1

Status: Implemented release candidate; local Python 3.12 and 3.13 gates passed
Owner: Ebrahim / Codex orchestrator
Date: 2026-07-10
Run ID: `20260710-oss-harness-v01`

Implementation evidence: the durable, batch-by-batch records are in [`../reviews/`](../reviews/).

## Concrete Definition

Build a local-first Python OSS harness that gives any compatible model or agent the same source-grounded study behaviour through an event-sourced state kernel, versioned skills, declarative playbooks, stable domain APIs, and typed tools, without depending on Sbobby Web, a hosted product, a specific provider, or a specific agent framework.

## Goal

Publish the smallest credible study-agent contribution that proves the reusable architectural spine end to end:

```text
create local course
-> ingest text/Markdown sources
-> index retrievable source spans
-> execute the same grounded-answer skill/playbook with any conforming model
-> return a structured answer with resolvable citations
-> persist and resume the study session
-> rebuild the same domain state from its event log
```

The first release is `0.1.0`, not the complete TutorKit product. It contains the minimal state kernel and skill/playbook machinery needed to prove the architecture. Later releases add study artifacts, SRS, assessment, planning, richer pedagogical playbooks, learner modelling, richer ingestion, and longitudinal evaluation without changing these boundaries.

## Problem

The repository contains effective but separate study methods: transcription and source preparation, RAG, flashcard generation and audit, Anki workflows, SRS, simulations, visual identification, and multiple study applications. They are not exposed through one reusable, provider-neutral study-agent contract.

The Fable TutorKit draft contains a valuable north-star architecture, but its extended v1 combines the kernel, hosted infrastructure, real-time voice, collaboration, marketplace, sync, calendars, and advanced privacy into one release. The exported draft is also incomplete. Implementing it literally would create a large new platform before proving the core contribution.

## Users

- Library author integrating study capabilities into an existing agent or application.
- Researcher comparing models, runtimes, prompts, and retrieval configurations on the same study workflow.
- Advanced learner running the reference CLI against local material.
- Future Sbobby product code, as a downstream consumer after the OSS contribution stabilizes.

## User Stories

- As a library author, I can call study services directly or expose their typed manifests to my agent without adopting a particular runtime.
- As a model-adapter author, I can implement one conformance-tested protocol without changing study-domain code.
- As a researcher, I can rerun the same grounded-answer fixture with different model/runtime configurations and compare structured results.
- As a learner, I can add local notes, ask a question, inspect exact supporting spans, stop the process, and resume the session later.
- As a downstream product author, I can replace local storage and CLI composition without forking course, source, citation, or grounding semantics.

## Design Principles

1. **Study domain before agent framework.** Course, source, citation, session, artifact, and evaluation contracts cannot import Tau or another agent SDK.
2. **Models are guests.** A model is selected through a capability-declaring port; no domain entity contains provider-specific configuration.
3. **Agents use ordinary services.** Every study operation is callable in-process and may also be described as a typed tool. The core does not require an autonomous loop.
4. **Grounding is an observable contract.** A grounded answer either resolves its claims to source spans or reports insufficient support.
5. **Local-first and inspectable.** SQLite and local content storage are the reference adapters. No account or server is required.
6. **Deterministic where possible.** Ingestion, hashing, retrieval, validation, persistence, and citation resolution are code; the model handles linguistic transformation.
7. **The event log is domain truth.** Every canonical mutation appends a versioned domain event; query state is a projection that must be rebuildable from the log. Blobs, model traces, checkpoints, and search indexes have explicit ownership outside the domain log.
8. **Skills describe capability; playbooks describe execution.** Study behaviour is versioned independently from models. Model adapters translate transport and streaming only; they do not contain pedagogical branches or model-specific study procedures.
9. **Capability negotiation replaces model branching.** Skills and playbooks declare required capabilities. A model/runtime satisfies them, activates an explicitly declared portable fallback, or fails before execution.
10. **One distribution before package proliferation.** Internal modules have strict boundaries, but the first release is one installable Python distribution.
11. **No silent product scope.** Web UI, authentication, multi-tenancy, billing, mobile sync, and the Sbobby rewrite remain outside this contribution.

## In Scope

- Python 3.12+ library with strict typing and a small reference CLI.
- Course profile creation with exam metadata and structured study policy.
- Immutable ingestion of UTF-8 text and Markdown sources.
- Deterministic chunking with stable source-span locators and checksums.
- Append-only, versioned domain event store with synchronous projections, snapshots, and replay verification.
- Retrieval port plus a local lexical/SQLite FTS reference adapter.
- Citation resolution back to exact source spans.
- Versioned prompt contract for grounded question answering.
- Structured answer schema distinguishing supported content, synthesis, uncertainty, and unsupported requests.
- Provider-neutral model port with capability metadata.
- Versioned skill packages containing prompt composition, schemas, policies, tool/capability requirements, validators, and eval fixtures.
- Minimal declarative playbook AST and engine supporting sequential `tool`, `model`, `dialogue`, and `validate` steps.
- Persistent `PlaybookRun` checkpoints with pinned skill, playbook, prompt, tool, model-adapter, and state versions.
- Fake/scripted model adapter for deterministic tests.
- One opt-in OpenAI-compatible adapter usable with DeepSeek, OpenRouter, or a local compatible endpoint.
- Persistent local sessions represented through domain events, resumable context summaries, and linked playbook runs.
- Framework-neutral typed tool registry for external agents.
- Reference harness that executes built-in skills through the playbook engine, beginning with grounded Q&A; it is not a general autonomous-agent framework.
- Evals for schema adherence, citation integrity, unsupported-answer behaviour, prompt injection resistance, session continuity, and adapter conformance.
- Export of course metadata, source manifests, sessions, and audit records as documented JSON/JSONL.

## Out of Scope

- Rewriting or extending `sbobby-web` or the Swift application.
- Authentication, accounts, collaboration, tenancy, billing, hosted APIs, or product analytics.
- PDF, OCR, audio, ASR, diarization, voice conversations, or multimodal model input.
- Vector retrieval, reranking, PageIndex, knowledge graphs, or a mandatory RAG framework.
- Flashcard generation, Anki integration, FSRS, quizzes, oral simulations, study planning, or learner mastery.
- Playbook loops, conditions, nested composition, transactional step groups, parallel branches, marketplace packaging, untrusted third-party playbooks, or licensing enforcement. The v0.1 subset is sequential and trusted.
- Multi-device sync, Postgres, calendars, crypto-shredding, or disaster-recovery infrastructure.
- MCP or HTTP servers. The tool manifest is designed so these transports can be added later.
- Distributed event ordering, multi-writer merge, or offline command reconciliation.
- Selecting Tau as a mandatory dependency or copying Tau source before an explicit adoption ADR.

## Repository and Module Shape

Working repository name: `study-agent-harness` until publication naming is decided.

```text
study-agent-harness/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/study_agent/
│   ├── domain/          # provider/framework-free entities and value objects
│   ├── ports/           # event store, retrieval, model, clock, run and tool protocols
│   ├── application/     # use cases; transaction and authorization boundaries
│   ├── state/           # event registry, reducers, projections, snapshots and replay
│   ├── ingestion/       # text/Markdown ingestion and deterministic chunking
│   ├── retrieval/       # retrieval services and local FTS adapter
│   ├── grounding/       # answer schema, citation resolver and validators
│   ├── prompts/         # versioned prompt definitions and composition
│   ├── skills/          # portable study capabilities and registry
│   ├── playbooks/       # declarative AST, engine, checkpoints and traces
│   ├── sessions/        # session lifecycle, summaries and run records
│   ├── tools/           # framework-neutral typed tool registry
│   ├── adapters/        # SQLite, filesystem, model and optional runtime bridges
│   ├── evals/           # fixtures, assertions and comparative reports
│   └── cli/             # reference CLI composition only
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── evals/
├── examples/
└── docs/
    ├── adr/
    ├── specs/
    └── compatibility/
```

Dependency direction:

```text
domain <- ports <- application <- adapters/cli
                         ^
          state/ingestion/retrieval/grounding/prompts/skills/playbooks/sessions/tools

evals may depend on public interfaces; production modules never depend on evals.
```

`domain`, `ports`, and `application` must not import provider SDKs, Tau, web frameworks, UI libraries, or retrieval frameworks.

## Domain Model

### CourseProfile

- `id`
- `title`
- `language`
- optional `exam_date`
- `assessment_styles`
- `learning_goals`
- `source_policy`
- `terminology_policy`

Course-specific behaviour is structured data composed into prompts. It is never implemented as scattered prompt branches.

### SourceDocument

- immutable `source_id` and `revision_id`;
- `kind`, title, media type, checksum, byte length, creation timestamp;
- trust level and source role;
- original local blob reference;
- structure origin and ingestion method.

Uploading changed content creates a new revision. No API overwrites an existing source revision.

### SourceChunk

- stable chunk id derived from source revision, span, and chunker version;
- exact character offsets into normalized extracted text;
- section path and ordinal;
- checksum and optional metadata;
- no provider embedding objects.

### Citation

- source id and revision id;
- chunk id;
- exact character offsets;
- human-readable locator;
- optional quoted snippet generated by the resolver from canonical stored text.

### StudySession

- course id;
- started/ended timestamps from `ClockPort`;
- append-only interaction records;
- structured continuation summary;
- model/runtime configuration snapshot for each model run.

The summary is not the source of truth for earlier turns; it is a compact continuation artifact linked to the underlying interaction records.

### DomainEvent and Projections

Every canonical mutation is expressed as a typed `DomainEvent` with:

- globally unique event id and per-course monotonic sequence;
- event type and schema version;
- course, optional session, causation, and correlation identifiers;
- trusted actor/principal metadata;
- timestamp from `ClockPort`;
- validated payload carrying required epistemic metadata.

The reference SQLite adapter is single-writer per course. Appending events and updating synchronous projections occurs in one transaction. Reducers are deterministic and side-effect-free. Rebuilding projections from event zero must produce domain-equivalent state; indexes, snapshots, and operational traces may be regenerated separately.

### SkillPackage

A skill is a portable, versioned study capability. It contains:

- id, semantic version, purpose, and engine compatibility range;
- input and output schemas;
- layered prompt definitions;
- course-profile fields consumed;
- grounding and state-write policies;
- required model capabilities and typed tools;
- referenced playbook;
- validators, known failure modes, and eval fixtures.

The first built-in package is `grounded_answer@1`.

### PlaybookDefinition and PlaybookRun

A playbook is the model-independent execution procedure used by a skill. The v0.1 AST supports a validated sequential list of:

- `tool`: deterministic typed tool call;
- `model`: canonical `ModelRequest` plus structured output contract;
- `dialogue`: suspend and request external human input;
- `validate`: deterministic validator over previous outputs.

`PlaybookRun` pins skill, playbook, prompt, tool-behaviour, model-adapter, and state versions. A run checkpoint is operational state owned by `RunStore`; lifecycle transitions emit domain events when they affect the study session. Resume rejects incompatible pins or stale declared read dependencies.

### GroundedAnswer

- answer status: `answered | insufficient_evidence | conflicting_evidence | failed`;
- typed segments: `supported_claim | synthesis | uncertainty | study_guidance`;
- citations per supported claim and synthesis premise;
- explicit unsupported-information note;
- prompt, model, retrieval, and validator provenance.

`study_guidance` may instruct the learner how to study supplied content but cannot introduce uncited domain facts.

### Epistemic Metadata

The north-star three-axis distinction is preserved:

- `ContentOrigin`: original, extracted, reworked, generated, inferred;
- `ClaimOrigin`: declared, observed, inferred;
- `StructureOrigin`: source-authored, mechanically extracted, model-proposed, human-approved.

Only `ContentOrigin` and `StructureOrigin` are exercised deeply in v0.1. `ClaimOrigin` is included in the stable vocabulary for later learner-model work but is not used to estimate mastery.

## Public Port Contracts

Illustrative Python shapes; the implementation may refine field names without weakening semantics.

```python
from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping, Protocol

class BlobStore(Protocol):
    def put(self, content: bytes) -> BlobRef: ...
    def get(self, ref: BlobRef) -> bytes: ...

class SourceContentPort(Protocol):
    def get_text(self, revision_id: str) -> str: ...
    def resolve(self, citation: Citation) -> ResolvedCitation: ...

class RetrievalPort(Protocol):
    def index(self, chunks: Sequence[SourceChunk]) -> IndexReceipt: ...
    def search(self, query: RetrievalQuery) -> RetrievalEvidenceSet: ...

class ModelPort(Protocol):
    @property
    def capabilities(self) -> ModelCapabilities: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

class EventStore(Protocol):
    def append(
        self,
        course_id: str,
        expected_seq: int,
        events: Sequence[DomainEvent],
    ) -> AppendReceipt: ...
    def read(self, course_id: str, after_seq: int = 0) -> Sequence[DomainEvent]: ...

class RunStore(Protocol):
    def save(self, checkpoint: PlaybookCheckpoint) -> None: ...
    def load(self, run_id: str) -> PlaybookCheckpoint: ...

class SessionViewPort(Protocol):
    def load(self, session_id: str) -> StudySessionRecord: ...

class StudyTool(Protocol):
    @property
    def manifest(self) -> ToolManifest: ...
    async def invoke(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> ToolResult: ...

class StudyHarness(Protocol):
    async def ask(
        self,
        course_id: str,
        session_id: str,
        question: str,
        mode: str = "grounded",
    ) -> AsyncIterator[StudyEvent]: ...
```

`ModelPort` is deliberately narrow. An implementation may adapt Tau, an OpenAI-compatible endpoint, or another SDK, but may only translate canonical messages, tool calls, structured-output constraints, usage, cancellation, and stream events. Model-specific tutoring prompts, state rules, retrieval policy, or grading logic are forbidden in model adapters.

### ExecutionContext

`ExecutionContext` is constructed by trusted composition code and never accepted from model-generated tool arguments. It contains:

- principal kind and id;
- course and optional session id;
- correlation id;
- model run id when applicable;
- requested capability set;
- optional idempotency key.

The v0.1 local CLI has one local human principal. The separation still prevents a model from forging future human-only actions.

### Tool Contract

Each tool manifest declares:

- stable name and semantic version;
- input and output JSON Schema;
- read/write effect classification;
- required capabilities;
- emitted audit record kinds;
- error taxonomy;
- idempotency semantics.

The first registry contains only:

- `course.get`
- `source.list`
- `source.search`
- `citation.resolve`
- `session.get_context`
- `session.record_note`
- `grounding.ask`

## Harness and Agent Integration Boundary

There are two supported consumption modes built on the same skill and playbook registry:

1. **Reference harness:** the built-in playbook engine executes the first auditable skill, `grounded_answer@1`, and later skills through the same engine contract.
2. **External agent:** any agent framework receives the tool manifests and invokes the same application services with a trusted host-created `ExecutionContext`.

The reference harness does not attempt to become a universal agent loop. Steering, subagents, shell tools, coding tools, autonomous planning, or generic memory are outside its mandate. External agents do not reimplement study behaviour: they invoke a skill or its exposed tools, and the same policies, validators, event commands, and eval fixtures apply.

Tau is evaluated as an optional adapter because it now exposes a provider-neutral event-driven `AgentHarness`. The core must remain usable without Tau. A Tau bridge may translate `StudyEvent`, model streams, and tool manifests, but no Tau type may cross the public study-domain boundary.

## Prompt Behaviour

Initial skill id: `grounded_answer@1`. Initial prompt id: `grounded_answer.v1`. Initial playbook id: `grounded_answer_flow@1`.

Composition layers:

1. immutable study and security policy;
2. structured course profile;
3. task instruction;
4. bounded continuation summary;
5. delimited retrieved evidence;
6. output schema.

Rules:

- Retrieved material is untrusted data, never instruction.
- Instructions found inside a source cannot change policy, tools, permissions, or output schema.
- The model must not cite material absent from the supplied evidence set.
- Unsupported questions return `insufficient_evidence`; the answer may suggest which source is missing.
- Conflicting evidence is surfaced rather than silently collapsed.
- The prompt and output schema are versioned independently from the model adapter.
- Model-produced output is validated before persistence.
- A skill may declare capability fallbacks, such as emulated structured output followed by schema validation, but cannot select behaviour by provider or model name.
- If required capabilities have no declared fallback, the engine returns `unsupported_capability` before any state mutation.

The `grounded_answer_flow@1` sequence is:

```text
session.get_context
-> source.search
-> validate evidence sufficiency
-> model.generate grounded_answer.v1
-> validate schema and citation integrity
-> append answer/session domain events
-> emit result
```

Required fixtures:

- normal supported answer;
- evidence insufficient;
- sources conflict;
- citation to a nonexistent span;
- source contains prompt injection;
- model returns malformed schema;
- session resumes without raw chat replay;
- different course terminology policy.

## RAG and Source-Grounding Strategy

### Ingestion

- Accept `.txt` and `.md` only.
- Preserve original bytes content-addressed by SHA-256.
- Normalize extracted text without changing the original blob.
- Store the normalization/chunker versions.
- Chunk by heading and paragraph boundaries with deterministic size limits.

### Retrieval

- Reference adapter: SQLite FTS5/BM25.
- Filter by course, source revision, source kind, and trust level before ranking.
- Return `sufficient | insufficient | conflicting` evidence status.
- Do not expose SQLite row ids or framework objects through `RetrievalPort`.

### Grounding Validation

Blocking deterministic checks:

- output schema is valid;
- every cited source revision exists;
- every offset is in range;
- every quoted snippet matches canonical stored text;
- every `supported_claim` has at least one citation;
- `insufficient_evidence` output contains no supported claims;
- no model-provided citation can alter stored source metadata.

Entailment between claim and citation is evaluated through calibrated fixtures and optional judges. It is not misrepresented as a perfect deterministic runtime guarantee in v0.1.

## Persistence

Reference storage is one SQLite database plus a content-addressed local blob directory.

The canonical domain source of truth is the append-only `events` table. Projection tables store courses, source manifests, chunks, sessions, answers, and continuation summaries for reads. Appending an event batch and updating synchronous projections share one SQLite transaction. Projection tables cannot be written through public application APIs.

Operational tables store playbook checkpoints, model run manifests, validation traces, and retrieval diagnostics. Their lifecycle is explicit; they are not silently treated as domain truth. Original blobs are content-addressed and referenced by immutable source events.

Provider calls and other external I/O occur outside domain transactions. A playbook persists its operational intent and pins, performs the external step, then commits validated domain events with an idempotency key. Crash recovery resumes or safely retries according to the step behaviour manifest.

Replay verification deletes projections in a temporary database, reduces the event stream, rebuilds derived indexes, and compares canonical serialized projection state byte-for-byte for the same event schemas and reducer versions. Snapshots accelerate startup but are invalidated on reducer or schema incompatibility.

No Postgres parity is claimed in v0.1. Storage ports and conformance tests are designed so an external adapter can be implemented later.

## Error Taxonomy

- `invalid_input`
- `not_found`
- `conflict`
- `unsupported_capability`
- `insufficient_evidence`
- `source_integrity_error`
- `retrieval_error`
- `model_unavailable`
- `model_protocol_error`
- `validation_error`
- `persistence_error`
- `cancelled`
- `budget_exceeded`

Errors returned to callers are structured and safe. Original provider errors may be retained in local diagnostic records with secrets redacted, but do not become public contract fields.

## CLI Contract

Working command name: `study-agent`.

```text
study-agent init <directory>
study-agent course create --title ... [--exam-date ...]
study-agent source add <course-id> <path>
study-agent source list <course-id>
study-agent ask <course-id> "question"
study-agent session list <course-id>
study-agent session resume <session-id>
study-agent export <course-id> --output <path>
study-agent doctor
```

Human-readable output is the default. Commands that return domain data support `--json`. Commands do not require network access except `ask` with a non-local configured model.

### CLI Experience States

- Long ingestion, retrieval, and model operations expose a concise progress state without corrupting JSON output.
- Empty course/source/session lists return a successful empty result, not an exception.
- Missing evidence is a normal structured outcome; provider or persistence failure is a non-zero command error.
- Cancellation leaves no partial domain mutation and records a cancelled run when a run already exists.
- `NO_COLOR` and non-interactive terminals are respected; essential information never depends on colour, cursor motion, or Unicode symbols.

## Security and Privacy Invariants

- Original source bytes are never overwritten.
- No secret or provider credential is persisted in course/session exports.
- Source content is always treated as untrusted model input.
- Tool authorization context cannot be supplied by the model.
- Model adapters receive only the evidence and session fields selected by application policy.
- Tests and default telemetry do not transmit user material.
- The core has no telemetry enabled by default.
- Local deletion semantics are documented honestly; crypto-shredding is not claimed.

## Acceptance Criteria

- [x] A clean Python 3.12 environment can install the distribution and run the CLI.
- [x] Domain and port modules import without Tau or provider SDKs installed.
- [x] All canonical course/source/session/answer mutations append typed events and update projections atomically.
- [x] Projection deletion followed by event replay reconstructs byte-identical canonical serialized state for the same schema/reducer versions.
- [x] A course and two text/Markdown sources can be created locally.
- [x] Re-ingesting unchanged bytes is idempotent; changed bytes create a new immutable revision.
- [x] FTS retrieval returns resolvable citations with stable spans.
- [x] A fake model drives the complete grounded-answer flow deterministically.
- [x] The identical `grounded_answer@1` skill and `grounded_answer_flow@1` playbook run with the fake adapter and the opt-in real adapter; no model-specific prompt or domain branch exists.
- [x] An opt-in OpenAI-compatible smoke can use DeepSeek without changing domain or prompt contracts.
- [x] Unsupported evidence produces `insufficient_evidence` without invented citations.
- [x] A prompt-injection string inside a source cannot alter the tool set or output schema.
- [x] Closing and resuming a session preserves continuity without requiring the original chat transcript in the model context.
- [x] A playbook can suspend at a dialogue boundary and resume from a pinned checkpoint, while an incompatible checkpoint fails explicitly.
- [x] The same `grounding.ask` use case works through the reference harness and direct typed-tool invocation.
- [x] Every persisted generated answer records source, prompt, model, retrieval, and validator provenance.
- [x] Export contains documented course/session/source manifests and excludes credentials.
- [x] Unit, contract, integration, and deterministic eval suites pass without external API keys.
- [x] The public API documentation includes one external-agent integration example.

## Verification

- Unit: event reducers, replay, hashing, normalization, chunking, citations, skill/playbook schemas, capability negotiation, prompt assembly, session reduction, idempotency, and redaction boundaries.
- Contract: every port has a reusable conformance suite; every skill, playbook, and tool validates schemas, version pins, JSON input/output, effects, and error shapes.
- Integration: temporary local repository from init through ingest, ask, session resume, and export.
- Evals: deterministic fake-model fixtures plus opt-in DeepSeek smoke; no network eval is a default CI requirement.
- Architecture: import-boundary check forbids provider, Tau, storage, or CLI imports from domain/ports.
- Manual: run the CLI against a small medical text and inspect citations and resumed context.

## Release Roadmap

### 0.1 — Grounded session spine

This specification.

### 0.2 — Study artifacts and richer retrieval

- versioned notes, explanations, summaries, and flashcards with provenance;
- vector/reranking adapters and PDF ingestion;
- MCP/HTTP tool transport if justified by real consumers.

### 0.3 — Recall and SRS

- first-class flashcards, review log, scheduler port, FSRS adapter;
- Anki export as an integration, never canonical scheduling state.

### 0.4 — Assessment and learner evidence

- MCQ/open/oral text attempts;
- reasoning and confidence capture;
- gaps, misconceptions, and deterministic mastery estimates from evidence.

### 0.5 — Planning and advanced pedagogical procedures

- negotiable study plans;
- playbook loops, conditions, transactional groups, richer dialogue, and composition;
- remediation and intervention outcomes;
- expanded scenario and longitudinal evals.

### 1.0 — Stable OSS contribution

- stable public contracts and migration policy;
- at least two model adapters and two agent/runtime integrations;
- local export/import and compatibility documentation;
- calibrated core eval suite and release gates;
- contributor-ready documentation and examples.

### Beyond the OSS core

Audio/diarization, real-time voice, Postgres, multi-device sync, collaboration, calendar integration, marketplace, crypto-shredding, and the Sbobby product are separate downstream tracks. They may influence ports, but they do not enter the OSS critical path until a real core use case requires them.

## Risks

- **Generic-agent drift:** mitigated by keeping the reference harness limited to study procedures and externalizing generic runtime concerns.
- **Tau coupling:** mitigated by an optional adapter and import-boundary tests.
- **Premature DSL complexity:** mitigated by a deliberately small sequential AST in 0.1, conformance fixtures, and no loops or parallelism until real procedures require them.
- **Grounding theatre:** mitigated by separating deterministic citation integrity from probabilistic entailment evaluation.
- **Premature abstraction:** mitigated by one vertical use case and one distribution before multiple packages/transports.
- **Scope re-expansion:** mitigated by release-specific acceptance criteria and explicit roadmap placement.
- **Medical correctness expectations:** v0.1 proves source fidelity, not independent clinical correctness; examples are educational and not medical advice.

## Decision Log

- 2026-07-10: OSS contribution is the sole current target; product work follows later.
- 2026-07-10: `sbobby-web` is neither rewritten nor used as the first implementation target.
- 2026-07-10: TutorKit extended-v1 capabilities become a roadmap, not one release gate.
- 2026-07-10: core and public contracts are model-, provider-, runtime-, and agent-agnostic.
- 2026-07-10: DeepSeek is allowed for inexpensive prototyping only through a generic adapter.
- 2026-07-10: Python is retained as the preferred implementation language from the accepted OSS-harness ADR.
- 2026-07-10: Tau is a candidate optional runtime adapter; adoption or source extraction needs a separate ADR.
- 2026-07-10: corrected after review — event-sourced canonical domain state and replayable projections are foundational requirements from 0.1.
- 2026-07-10: corrected after review — a minimal versioned skill/playbook layer is foundational from 0.1 so pedagogical behaviour does not move into per-model adapters.
- 2026-07-10: approved by the project owner for implementation.

## Required Supporting Work

- ADR: the OSS-only ADR remains authoritative; accepted ADR-0002 defines event-sourced state and the skill/playbook boundary. Separate ADRs remain required for Tau adoption and final license choice.
- Prompt eval fixtures: required.
- RAG/source-grounding tests: required and release-blocking.
- UI states: not applicable; CLI output/error behaviour is specified instead.
- Data migration: none for 0.1; new local format must include `schema_version` from the start.
- Worker decomposition: required before implementation.

## Open Questions That Do Not Block Spec Review

- Final public project/package name.
- OSS license for original project code.
- Whether the first real-model adapter is implemented directly against an OpenAI-compatible API or through an optional Tau bridge.
- Whether the initial repository is created inside this workspace or as a separate sibling Git repository.

## Draft Task Beads

| Task id | Title | Depends on |
|---|---|---|
| `harness-repo-bootstrap` | Create Python package, CI-quality tooling, import-boundary checks, and contributor skeleton | — |
| `tau-compatibility-spike` | Compare direct model adapter vs optional Tau bridge and write adoption ADR | `harness-repo-bootstrap` |
| `core-domain-contracts` | Implement course, source, chunk, citation, session, answer, provenance, event, error, and execution-context types | `harness-repo-bootstrap` |
| `event-state-kernel` | Implement event registry, SQLite event store, reducers, projections, snapshots, replay, and conformance tests | `core-domain-contracts` |
| `local-content-store` | Implement content-addressed blob storage and source-integrity contracts | `core-domain-contracts` |
| `text-ingestion` | Implement immutable text/Markdown ingestion, normalization, deterministic chunking, and source-revision events | `event-state-kernel`, `local-content-store` |
| `fts-retrieval` | Implement retrieval/citation ports and SQLite FTS adapter with sufficiency outcomes | `text-ingestion` |
| `skill-package-contract` | Implement skill manifest, layered prompts, capabilities/fallbacks, validators, and fixture registry | `core-domain-contracts` |
| `minimal-playbook-engine` | Implement sequential AST, version pins, steps, checkpoints, suspend/resume, and traces | `event-state-kernel`, `skill-package-contract` |
| `grounded-answer-skill` | Implement `grounded_answer@1`, prompt/output schemas, playbook, validators, and adversarial fixtures | `fts-retrieval`, `minimal-playbook-engine` |
| `model-adapter-contract` | Implement fake adapter and selected optional real-model adapter behind `ModelPort` | `core-domain-contracts`, `tau-compatibility-spike` |
| `session-harness` | Integrate session lifecycle, continuation summaries, playbook runs, and grounded `ask` | `grounded-answer-skill`, `model-adapter-contract` |
| `typed-tool-registry` | Expose study use cases through framework-neutral JSON-schema tools and trusted execution context | `session-harness` |
| `reference-cli` | Implement init/course/source/ask/session/export/doctor commands with JSON mode | `typed-tool-registry` |
| `v0.1-eval-release` | Complete conformance suites, end-to-end fixtures, docs, examples, packaging, and release gates | all preceding implementation beads |
