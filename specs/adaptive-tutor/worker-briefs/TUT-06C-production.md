# Worker Brief: TUT-06C host-bound file snapshots

## Assignment

Implement `TUT-06C` only after TUT-06B is green and accepted. Reuse the same
Luna implementer context, but treat this as a separate high-risk file-trust
phase with its own focused gates.

## Worker Profile

Reuse `docs/worker-profiles/reference-tutor-host-worker.md`.

## Read First

- `AGENTS.md`
- `dev/plans/2026-07-18-1145--adaptive-tutor--tut06-batch-a--plan.md`
- `specs/adaptive-tutor/beads/TUT-06C-host-bound-file-snapshots.md`
- `src/study_agent/hosts/contracts.py`
- accepted TUT-06B runner/port implementation
- `src/study_agent/ports/source_input.py`
- `src/study_agent/adapters/filesystem/source_input.py`
- `src/study_agent/ingestion/service.py`
- `src/study_agent/ingestion/identity.py`
- `tests/contract/filesystem/test_source_input.py`
- `tests/contract/ports/test_source_input_contract.py`

## Allowed Files

You may change:

- `src/study_agent/hosts/files.py`: strict snapshot/content/ref/command contracts
  and trusted registry/service.
- `src/study_agent/hosts/__init__.py`: explicit exports.
- `src/study_agent/ports/host_file.py`: identity/store/ingestion protocols.
- `src/study_agent/ports/__init__.py`: explicit exports.
- `src/study_agent/adapters/memory/host_file.py`: create the bounded operational
  byte store at this exact destination.
- `src/study_agent/adapters/memory/__init__.py`: explicit export.
- `tests/unit/hosts/test_host_file_snapshots.py`.
- `tests/contract/hosts/test_host_file_contracts.py`.
- `tests/integration/test_host_file_snapshots.py`.
- `tests/architecture/test_tutor_host_boundaries.py`.

Do not change:

- `SourceInputPort`, `FilesystemSourceInput`, `TextIngestionService`, existing
  TUT-06A/B public decision/runner behavior, capability gateway/contracts,
  domain/state/events, source/ingestion schemas, skills/playbooks/prompts,
  StudyTools, CLI, dependencies, docs/specs, `sbobby-web`, or unrelated tests.

## Required Public Contract

### Values

- `HostFileSnapshot`: opaque host file id, exact `CourseId`, exact `SessionId`,
  sanitized display name, canonical media type (`text/plain` or
  `text/markdown`), original `.txt`/`.md` filename without path, byte size,
  lowercase SHA-256, exact captured bytes, aware `captured_at`, aware
  `expires_at`. Constructor verifies UTF-8, checksum/size, media-extension
  agreement, `captured_at < expires_at`, bounds, and no path components.
- `HostFileReference`: course/session/id/checksum only; safe for trusted lookup,
  never bytes/path.
- `UntrustedHostFileContent`: exact bytes plus display/media/checksum and an
  explicit untrusted-content marker; this type is returned only to trusted host
  code, never placed in `TutorHostContext`.
- `TrustedHostFileIngestionCommand`: reference plus host-supplied `SourceId`,
  title, trust level, source role, `ExecutionContext`, and optional expected
  sequence. Reject owner mismatch and context course/session mismatch before
  invoking ingestion.
- Every operational value has an exact bounded canonical codec where stored;
  unknown fields, noncanonical bytes, changed checksum, timestamps, or owner
  fail closed.

### Ports

- `HostFileIdentityPort.issue(course_id, session_id, checksum,
  declaration_fingerprint) -> str`: stable exact retry, different bytes imply a
  different opaque id; model cannot call or supply it.
- `HostFileSnapshotStore.create(file_id, payload) -> bool` and `load(file_id) ->
  bytes`; identical retry is resolved by the registry, changed bytes conflict.
- `HostFileIngestionPort.ingest(...)`: structural protocol matching only the
  required `TextIngestionService.ingest` keyword arguments/result. This keeps
  the host package from importing a concrete application service.

### Registry/service

- Constructor receives `SourceInputPort`, identity port, snapshot store,
  `ClockPort`, positive TTL, max snapshot count, and max aggregate stored bytes.
  Require `max_snapshot_count <= MAX_HOST_FILES` and
  `max_aggregate_bytes <= MAX_TOTAL_SOURCE_BYTES`; retain the existing
  `MAX_SOURCE_BYTES` per-file bound.
- `capture(relative_path, course_id, session_id, display_name)` delegates the
  filesystem read exactly once to `SourceInputPort.snapshot`; it never opens,
  stats, resolves, watches, or rereads paths itself.
- Derive media type only from captured `.txt`/`.md` filename using existing
  ingestion semantics. Do not accept a model/caller media override.
- Issue trusted opaque id after successful capture, store canonical snapshot,
  and return only `HostFileDescriptor`. Identical retry returns identical
  descriptor; same id with changed bytes/owner/declaration conflicts.
- `lookup(reference)` checks id, course, session, checksum, canonical stored
  bytes, and `clock.now() < expires_at`, then returns
  `UntrustedHostFileContent`. It never returns the original relative path.
- `ingest(command, ingestion_port)` performs exact lookup first, maps the stored
  original basename/content to the existing ingestion call, and supplies every
  source/trust/sequence/authority value only from the trusted command. It never
  infers them from content, descriptor, or decision output.
- Snapshot storage is operational only: no event, projection, export, learner
  evidence, artifact, capability, or StudyTool write.
- The bounded memory store rejects new distinct snapshots after count/byte
  limits before mutation; identical retries remain allowed. Expired entries are
  not silently reused. No eviction policy in v0.1.

TUT-06C does **not** add `file_id`, ingestion, or source role to
`TutorDecision`, capability manifests, or StudyTools. A trusted host may capture
and ingest explicitly; later product/adapters may expose a separately approved
model proposal without reopening this boundary.

## Acceptance Matrix

Tests must cover:

- `.txt` and `.md` exact capture, descriptor ordering/context assembly, strict
  UTF-8 and media mapping;
- identical capture retry, changed bytes -> new id, identity collision conflict,
  store reconstruction and canonical-byte tamper;
- lookup success and missing, forged id/checksum, cross-course, cross-session,
  expired, display/media/size/checksum/content/timestamp tamper;
- path traversal, absolute path, Windows path/device, symlink, intermediate
  symlink, FIFO/socket/non-regular, read race, oversized file, too many files,
  aggregate byte exhaustion; reuse existing filesystem tests rather than copying
  their implementation;
- model-visible context/descriptor contains no relative/absolute path,
  filesystem identity, bytes, principal, grants, source id, trust, role,
  sequence, execution context, credential, or provider metadata;
- ingestion bridge exact success/idempotency, stale expected sequence, and zero
  ingestion calls on every owner/checksum/expiry/tamper failure;
- no canonical event at capture/lookup; only explicit bridge ingestion may
  append the existing source event;
- import without filesystem/OpenAI/provider dependencies in neutral contracts.

## Verification

Run:

```bash
PYTHONPATH=.:src .venv/bin/python -m pytest -q tests/unit/hosts/test_host_file_snapshots.py tests/contract/hosts/test_host_file_contracts.py tests/integration/test_host_file_snapshots.py tests/contract/filesystem/test_source_input.py tests/contract/ports/test_source_input_contract.py tests/architecture/test_tutor_host_boundaries.py
.venv/bin/ruff check src/study_agent/hosts/files.py src/study_agent/ports/host_file.py src/study_agent/adapters/memory tests/unit/hosts/test_host_file_snapshots.py tests/contract/hosts/test_host_file_contracts.py tests/integration/test_host_file_snapshots.py tests/architecture/test_tutor_host_boundaries.py
MYPYPATH=src .venv/bin/mypy --strict src/study_agent/hosts/files.py src/study_agent/ports/host_file.py src/study_agent/adapters/memory tests/unit/hosts/test_host_file_snapshots.py tests/contract/hosts/test_host_file_contracts.py tests/integration/test_host_file_snapshots.py
git diff --check
```

## Stop Conditions

Stop and report instead of deciding if implementation requires:

- changing the closed TutorDecision union, a capability manifest, StudyTool,
  SourceInputPort, TextIngestionService, source event/schema, dependency, or
  supported format;
- a model-selected source id/title/trust/role/sequence/context;
- storing paths, filesystem identity, raw bytes, or authority in model-facing
  descriptors/context;
- ambient time/random, eviction policy, hosted persistence, or changes outside
  the allowed files.

## Report Back

Return files changed, exact codecs/ports/bounds, capture/lookup/ingestion
behavior, verification results, forbidden-boundary confirmation, and unresolved
items. Do not commit, update status, start TUT-06D, or delegate.
