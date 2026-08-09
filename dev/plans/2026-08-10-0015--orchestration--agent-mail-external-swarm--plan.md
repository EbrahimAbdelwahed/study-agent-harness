# Plan: Agent Mail external swarm dispatcher

Date: 2026-08-10 00:15
Area: orchestration

## Goal

Use the already-installed MCP Agent Mail CLI to coordinate independent
`codex exec` workers beyond the desktop thread's four-agent limit, while
keeping Beads authoritative and preventing shared-index or file-surface races.

## Scope

- In scope: manifest validation, separate Git worktrees, Agent Mail identities,
  exclusive reservations, bead-thread messages, Luna xhigh worker launch,
  local run state, and operator documentation.
- Out of scope: installing a persistent Agent Mail service, modifying global
  Codex configuration, automatically merging worker branches, bypassing bead
  dependencies, or dispatching workers from this side conversation.

## Approach

1. Record the primary-source Agent Mail contract and current local diagnosis.
2. Add a standard-library-only manifest-driven dispatcher with dry-run default.
3. Reject overlapping reservations and unsafe worktree targets before mutation.
4. Launch each worker in a separate branch/worktree with a pre-registered
   identity and lease, and require completion mail in the bead thread.
5. Verify manifest validation, overlap rejection, and dry-run output locally.

## Risks

- Agent Mail is advisory; the dispatcher must not place two writers in one
  worktree or rely on leases as a substitute for Git isolation.
- Blocked beads cannot safely be made ready by coordination tooling alone.
- A persistent daemon/global MCP configuration requires separate explicit
  approval and is not needed for the CLI-based dispatcher.

## Verification

- `python3 scripts/agent_mail_swarm.py validate config/agent-mail-swarm.example.json`
- `python3 scripts/agent_mail_swarm.py dispatch config/agent-mail-swarm.example.json`
- `python3 -m py_compile scripts/agent_mail_swarm.py`
- `git diff --check -- scripts/agent_mail_swarm.py config/agent-mail-swarm.example.json docs/maintainer/agent-mail-swarm.md dev/plans/2026-08-10-0015--orchestration--agent-mail-external-swarm--plan.md`
