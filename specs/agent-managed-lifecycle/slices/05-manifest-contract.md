# Slice 05: Manifest contract

Release: 0.2
Depends on: released slice 04

## Contract unlocked

An agent can express and structurally validate bounded desired intent without
opening or mutating a repository or reading source content.

## API seam

- `study_agent.lifecycle.contracts`: strict `LifecycleManifestV1`, desired
  repository/course/source values, canonical fingerprint, and bounds.
- CLI `manifest schema|validate [PATH]`.

The normative shape is
[`../fixtures/manifest-v1.json`](../fixtures/manifest-v1.json). Exact keys are:

- root: `schema_version`, `repository`, `courses`;
- repository: `path`, `model`;
- model when non-null: `adapter_id`, `credential_env`, `settings`;
- course: `course_id`, `title`, `language`, `exam_date`, `learning_goals`,
  `assessment_styles`, `sources`;
- source: `source_id`, `path`, `title`, `trust_level`, `source_role`.

All listed keys are required; `model`, `exam_date`, `source.title`, and
`model.credential_env` may be null. There are no implicit field defaults.
`repository.path` is a non-empty, non-dot relative path under the manifest
directory and identifies the repository to initialize/open. Model config is the
existing strict technical config: only the environment-variable name is stored,
secret-like settings are rejected, and an existing repository must match it
exactly or plan a conflict.

Bounds are normative: manifest ≤1 MiB; path/ID/language/role strings ≤256 code
points; titles ≤1,024; 0–128 courses; 1–64 learning goals of ≤2,048 code points;
0–32 assessment styles of ≤512; 0–1,024 sources per course and ≤4,096 total;
trust level 0–100; each source ≤16 MiB and all snapshots ≤512 MiB. Exam dates
are `YYYY-MM-DD` or null. The serialized repository model config must also fit
the existing 64 KiB config bound. Within `model.settings`, maximum nesting depth
is 16, total JSON nodes are ≤1,024, object/array members per container are ≤256,
keys are ≤128 code points, and string values are ≤4,096. Recursion, overflow,
and pathological-width failures map to one safe validation error.

Canonicalization rejects duplicate keys, invalid UTF-8, non-finite numbers,
unknown fields, blank/untrimmed text, duplicate IDs, absolute paths, `.`, and
`..`. Object keys are sorted; courses and sources are sorted by explicit ID;
learning goals and assessment styles preserve declared order. The fingerprint
is SHA-256 over domain-separated canonical UTF-8 JSON.

Manifest IDs are explicit. Source paths are lexical paths relative to the
manifest directory; this slice validates their shape but does not open them. V1
has no glob, include, URL, deletion, executable content, plugin, secret value,
authority field, or model-selected behavior.

## Runnable checkpoint

Validate a golden manifest and inspect its canonical fingerprint; reject
duplicate keys, unknown fields, non-finite numbers, duplicate IDs, absolute or
parent-traversing paths, secret-like fields, and oversized manifest structure.

## Verification

- Pure parsing and byte-stable canonical fingerprint fixtures.
- `schema` and structural validation produce no repository, source, model,
  credential, index, run, or network effect.
- Closed fields and explicit count/string-size bounds.
- Deep-nesting, wide-object/array, excessive-node, and recursion-error fixtures
  for arbitrary JSON inside `model.settings`.
- Architecture tests keep lifecycle intent out of domain event/projection types.

## Human review checkpoint

Review only the schema, bounds, and forbidden vocabulary. Remote sources, globs,
dynamic skills, config mutation, or source I/O require later slices or ADRs.
