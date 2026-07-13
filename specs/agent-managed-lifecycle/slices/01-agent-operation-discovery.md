# Slice 01: Agent operation discovery

Release: 0.1.1
Depends on: none
Status: Complete (2026-07-13)

## Contract unlocked

An automation client can discover the harness, CLI operations, side effects,
repository requirements, and exact StudyTool manifests without opening a
repository, loading credentials, rebuilding an index, or contacting a model.

## API seam

- `study_agent.cli.registry`: a closed `CommandRegistration` set with parser
  callback, handler, and serializable metadata. The argparse tree, dispatcher,
  and `agent-operations@1` JSON manifest consume the same registrations.
  Registration is CLI-local and intentionally cannot describe arbitrary DSL
  nodes, plugins, or runtime-loaded commands.
- `study_agent.tools.builtin`: pure `public_study_tool_manifests()` derived from
  the existing sole manifest definitions.
- CLI: `study-agent describe` and `study-agent tool list|describe` with the
  existing JSON success/error envelope.

Descriptors include command identity/version, arguments, effect classification,
offline/network behavior, idempotency, retry guidance, output contract version,
and verification command. They contain no credential values or host paths.

`agent-operations@1` has exact root keys `contract_version`, `harness_version`,
`repository_schema_versions`, `offline_default`, `commands`, `study_tools`, and
`operator_skill`. Each command has exact keys `name`, `version`, `summary`,
`effect`, `repository`, `network`, `idempotency`, `retry`, `arguments`,
`output_contract`, and `verification`. Effects use `read_only`, `local_write`,
`canonical_write`, `operational_write`, or `external_model`; repository uses
`none`, `optional`, or `required`; network uses `never` or `model_only`.

Each argument has exact keys `name`, `kind`, `value_type`, `required`,
`repeated`, `default_json`, and `secret`. `kind` is `positional` or `option`;
`value_type` is `string`, `path`, `integer`, `number`, `boolean`, or `json`.
StudyTool entries contain exact keys `manifest` and `fingerprint`, where
`manifest` is the existing `ToolManifest.to_json()` shape. `operator_skill` is
null until slice 04; when present it contains `id`, `version`, `fingerprint`, and
`extraction_command`. Lists are sorted by stable identity; contract output is
bounded to 64 commands and 64 arguments per command. Slice 04 closes the final
non-null operator-skill snapshot after registering the extraction command.

## Runnable checkpoint

```bash
study-agent --json describe
study-agent --json tool list
study-agent --json tool describe grounding.ask
```

All commands succeed in an empty directory with the network denied.

## Verification

- Snapshot the agent-operation manifest and exact seven StudyTool manifests.
- Validate the exact closed JSON shapes and enums above; unknown fields fail the
  contract test rather than becoming undocumented extensions.
- Assert every descriptor produces the expected argparse command and every
  parser command is represented exactly once in discovery.
- Assert existing StudyTool identities, schemas, effects, and fingerprints are
  unchanged.
- Assert discovery opens no SQLite files, reads no credential value, changes no
  filesystem state, and attempts no socket call.
- Assert stdout is one valid JSON document and errors remain machine-clean.
- Full existing contract and architecture suites remain green.

## Human review checkpoint

Review the JSON shape for sufficiency as an automation contract. Feedback may
rename fields before 0.1.1, but may not turn prose help into the canonical schema
or duplicate tool definitions.
