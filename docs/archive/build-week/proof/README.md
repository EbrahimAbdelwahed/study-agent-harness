# Build Week launch proof

This is a local, non-product visualizer for the deterministic offline anatomy
trace. Its displayed source, evidence, context, status, and parity values are a
checked-in projection of:

```bash
study-agent-demo --json
```

Serve this directory with a static HTTP server. The default view plays an
80-second, six-chapter sequence designed for the cue windows in
`docs/archive/build-week/build-week-narration-final.txt`. `?scene=1` through `?scene=6` freeze the
corresponding chapter for deterministic visual QA.

The proof is a product-direction visualization backed by the real offline trace.
It does not call a provider or add a new harness contract.

The optional Codex + Flywheel companion is `flywheel-index.html`. It plays a
deterministic 39-second, six-chapter trace of how the project used Codex:
human-approved spec → dependency-aware beads → bounded worker → real offline
CLI proof → risk-proportionate tests/reviews → durable handoff. It deliberately
uses a distinct demonstrative process interface, not the study-harness UI. Use
`?scene=1` through `?scene=6` to freeze a chapter for capture. Its terminal box
is a legible subset of the real `study-agent-demo` output; the labels and
evidence paths are projections of checked-in artifacts.
