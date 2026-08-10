# Agent Mail external swarm

## Outcome

The desktop thread keeps its built-in agent limit. Extra concurrency comes
from independent `codex exec` processes, each in its own Git worktree. MCP
Agent Mail supplies identity, bead-thread messages, and exclusive advisory
file leases; Beads remains the status and dependency authority.

This repository uses the already-installed `am` CLI directly. A persistent
Agent Mail HTTP service and a global Codex MCP entry are optional. The
dispatcher does not install either one and does not modify `br`.

Primary sources:

- [MCP Agent Mail repository and quickstart](https://github.com/Dicklesworthstone/mcp_agent_mail)
- [Agent Mail and Beads conventions](https://github.com/Dicklesworthstone/mcp_agent_mail#integrating-with-beads-dependency-aware-task-planning)
- [Worktree identity and reservations](https://github.com/Dicklesworthstone/mcp_agent_mail#git-based-project-identity-opt-in)
- [Rust operator cookbook](https://github.com/Dicklesworthstone/mcp_agent_mail_rust/blob/main/docs/OPERATOR_COOKBOOK.md)

## Why worktrees are mandatory

Agent Mail reservations are advisory. They prevent planned path overlap and
make conflicts visible, but they do not isolate the Git index. Two workers in
one worktree can still stage each other's changes. The dispatcher therefore
creates one branch and worktree per lane before registering the lease.

## Manifest contract

Copy `config/agent-mail-swarm.example.json` to a run-specific file. Enable
only lanes whose base commit and public contracts are stable. Each lane needs:

- one canonical repository and Agent Mail `project_key`;
- an exact base commit or reviewed branch;
- the canonical shared Beads database;
- a bead ID and worker brief;
- a memorable Agent Mail name such as `AmberQuartz`;
- exclusive repository-relative paths that do not overlap another lane;
- exact verification commands.

The same bead may have multiple lanes only when the work packages are truly
independent. All lanes use the bead ID as the Mail thread. The primary bead
owner integrates the lane commits and alone closes the bead.

## Commands

Validate and inspect the wave:

```bash
python3 scripts/agent_mail_swarm.py validate path/to/wave.json
python3 scripts/agent_mail_swarm.py dispatch path/to/wave.json
```

Both commands are read-only. `dispatch` prints a plan unless explicitly armed:

```bash
python3 scripts/agent_mail_swarm.py dispatch path/to/wave.json --execute
```

Execution creates worktrees under `/private/tmp/agent-mail-swarm`, registers
the orchestrator and workers, acquires exclusive four-hour leases, opens one
mail thread per bead, and starts Luna xhigh `codex exec` workers. It never
merges, closes beads, deletes worktrees, or releases a crashed worker's lease.

Inspect local process state:

```bash
python3 scripts/agent_mail_swarm.py status path/to/wave.json
```

Inspect coordination state directly:

```bash
am robot reservations --project /absolute/project --all --conflicts --format toon
am robot thread BEAD-ID --project /absolute/project --agent SwiftCedar --format md
br --db /absolute/project/.beads/beads.db ready --json
```

## Four-hour sprint policy

- Dispatch only dependency-ready work or reviewed sub-lanes inside an active
  bead. Agent Mail does not make an unstable dependency safe.
- Prefer 6–8 implementation lanes, then reuse the capacity for tests and
  semantic reviews as commits arrive.
- Split by non-overlapping file ownership, not by vague roles.
- Keep one integration owner per bead. Workers do not merge or close it.
- If a worker crashes, inspect its branch, log, Mail thread, and active lease
  before releasing anything.

## Current local diagnosis

On 2026-08-10 the machine already had Agent Mail Rust `0.3.13` and Beads Rust.
The persistent service and Codex MCP entry were absent. An authenticated
service install was not performed because this workflow does not require it;
the CLI-backed dispatcher avoids global configuration and remains auditable.
