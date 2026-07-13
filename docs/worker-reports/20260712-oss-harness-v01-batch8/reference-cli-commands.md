# Worker Report: reference-cli-commands

Status: complete
Run ID: `20260712-oss-harness-v01-batch8`
Task: `docs/tasks/20260712-oss-harness-v01-batch8/reference-cli-commands.md`
Brief: `docs/worker-briefs/20260712-oss-harness-v01-batch8/reference-cli-commands.md`
Agent: reference_cli_impl
Reported: 2026-07-12 19:57

## Files Changed

- stdlib CLI parser/commands/output/entrypoint, packaging script, and independent CLI contracts

## Behavior Implemented

- All approved commands call canonical services with host-owned HUMAN authority and safe exact-one-document JSON output
- Descriptor-relative bounded source reads, honest index failure, offline doctor, and SIGINT boundary preserving committed outcomes

## Verification

- focused CLI: 54 passed; independent final audit: 23 passed
- full pytest: 414 passed, 1 expected skip
- Ruff/mypy/diff check/help smoke passed
- independent final semantic/security audit approved, no P0-P3

## Open Questions Or Blockers

- None.

## Follow-up Beads Needed

- None.
