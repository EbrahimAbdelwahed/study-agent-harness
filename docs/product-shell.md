# Build Week product shell

The product shell is a small, terminal-first consumer of the public tutor
contracts. It accepts a free-form learner entry before the context is complete,
then renders the current conversation, material snapshot, learner evidence
sequence, context conflicts, capability discovery, and optional due review.

The default journey is deterministic and offline:

```bash
study-agent-shell "I have ten minutes. Help me understand heart valves."
```

Use `--json` to inspect the same trace in scripts. The shell command reuses the
existing anatomy host trace; it does not create another tutor loop or write
canonical state. The optional TUT-07 due-review view is omitted safely when no
recall composition is installed.

## States shown to learners

`working` is emitted as soon as free-form text is accepted. Host suspension and
learner questions are visible as `suspended` or `needs_learner_input`.
Snapshot divergences are shown as `conflicted_context`; due items as
`needs_review`; stale, provider/interruption failure, and a successful refresh
as `stale`, `degraded`, and `recovered` respectively.

## Three-minute sample/eval/video script

1. (0:00–0:20) Enter the learner request with no onboarding form.
2. (0:20–0:55) Show the bundled material and evidence sequence.
3. (0:55–1:30) Show the host trace: complete, clarification suspension,
   evidence refresh, and recovered completion.
4. (1:30–2:05) Run `study-agent-shell --json` and point to capability
   discovery, parity, and the safe optional recall message.
5. (2:05–2:40) Run the focused tests, Ruff, and source mypy gate.
6. (2:40–2:55) Explain that SQLite and model/provider imports remain outside
   the shell; an API-key GPT-5.6 adapter is opt-in and never used by the
   offline path.

The implementation is terminal-only on purpose: it provides an accessible,
deterministic proof surface without adding a web framework or a second UI
state owner. A future browser consumer can use the same immutable view model.
