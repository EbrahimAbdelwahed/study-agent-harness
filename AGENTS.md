# AI Agent Instructions

Study Agent Harness is an embeddable, provider-neutral study runtime. Preserve
its canonical state, source-grounding, replay, approval, and recovery contracts.

## Required Git Workflow

- Treat the primary checkout and shared worktrees as read-only.
- Every task that changes files must use a dedicated Git worktree and a
  `codex/<task>` branch. Do not create a nested worktree when the task is already
  running in its own dedicated worktree.
- Start ordinary work from the latest `origin/main`. Use another base only when
  the task explicitly requires integration or recovery from that lineage.
- Inspect `git status` and `git worktree list` before editing. Never overwrite,
  stash, commit, or clean changes that belong to another user or agent.
- Keep commits intentional and reviewable. Do not mix unrelated changes.
- Run the narrowest relevant verification first, followed by broader project
  gates when practical.
- Push the task branch and open a pull request targeting `main` after
  verification. Never push directly to `main`.
- If push or pull-request creation is unavailable, stop with a verified local
  branch and commits ready, and document the exact blocker.

## Engineering Rules

- Be conservative with existing behavior and public contracts.
- Search the codebase and existing `dev/` memory before designing or editing.
- Prefer small, modular changes. Do not refactor unrelated code.
- Do not introduce dependencies unless they materially reduce risk or
  complexity. Keep provider, parser, scheduler, and observability integrations
  optional when possible.
- Canonical facts and human decisions belong to the harness. Model output is
  untrusted and cannot silently approve itself or mutate canonical state.
- Keep provider transports, persistence adapters, UI, and policy owners behind
  explicit ports. Do not leak their types into neutral domain contracts.
- Preserve deterministic replay: model calls and operational logs are not
  canonical state.
- Never hardcode credentials. Use environment references or host-provided secret
  resolvers.

## Natural-Language Processing

- The repository default for summarization, extraction, classification,
  rewriting, flashcard generation, quiz generation, explanations, semantic
  transformation, study assistance, and search enrichment is `gpt-5.6-luna`.
- Route model calls through dedicated adapters and `OPENAI_API_KEY` environment
  references. Do not use the `gpt-5.6` family alias.
- UI and domain components must not call model APIs directly.
- Prompts that affect study outputs must be versioned or documented and covered
  by loading, error, and evaluation paths.

## Development Memory

- Read `dev/index.md` when present, then search `dev/plans/`, `dev/logs/`,
  `dev/notes/`, `dev/decisions/`, and `dev/handoffs/` for relevant context.
- Create a plan before multi-file, architectural, uncertain, integration, or
  high-risk work.
- Record exact verification commands and outcomes in a log when work completes,
  fails, or remains partial.
- Create a handoff when work remains incomplete or context must carry forward.
- Keep memory granular and use
  `YYYY-MM-DD-HHMM--area--task--type.md` filenames.

## Verification

- Prefer the project commands declared in `pyproject.toml` and CI.
- Run focused tests before the full suite.
- Validate lint, strict typing, tests, and package build for substantive changes.
- Document pre-existing failures without hiding or weakening them.
- After medium-risk changes, obtain one independent semantic correctness and
  regression review. Use a security review for untrusted input, filesystem,
  networking, credentials, or sensitive serialization.
