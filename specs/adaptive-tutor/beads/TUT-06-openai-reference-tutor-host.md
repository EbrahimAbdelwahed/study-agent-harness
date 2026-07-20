# Task Bead: TUT-06 OpenAI reference tutor host

Status: Done
Priority: P0
Type: tracer-bullet
Depends On: TUT-03, TUT-05

## Worker Profile

reuse `model-adapter-worker`; create `reference-tutor-host-worker` after current
official OpenAI Responses documentation is captured

## Outcome

One provider-neutral bounded tutor host composes sequence-consistent evidence
and invokes the existing capability gateway. An optional API-key OpenAI
Responses adapter supplies host decisions without owning study behavior,
authority, retries, or canonical state.

## Acceptance Criteria

- [x] OpenAI imports are confined to optional host/technical adapter packages.
- [x] Scripted and live hosts exercise the same gateway contract.
- [x] Step budget, interruption, stale continuation, retry, and redaction are explicit.
- [x] File uploads become host-bound snapshots before agent visibility.
- [x] API-key mode is complete; subscription mode is not falsely emulated.
- [x] The base distribution remains dependency-free; the OpenAI SDK is one
  optional extra and its absence does not break core or scripted-host imports.
- [x] The OpenAI model id is explicit configuration, never a core capability or
  hard-coded provider branch.

## Decomposition

- [TUT-06A](TUT-06A-provider-neutral-tutor-host-contracts.md) — host contracts,
  redacted context, decision union, and authority boundary.
- [TUT-06B](TUT-06B-bounded-scripted-tutor-loop.md) — deterministic bounded
  runner over the existing gateway.
- [TUT-06C](TUT-06C-host-bound-file-snapshots.md) — immutable host-owned file
  capture before model visibility.
- [TUT-06D](TUT-06D-openai-responses-host-adapter.md) — optional direct OpenAI
  Responses decision adapter.
- [TUT-06E](TUT-06E-reference-host-closure.md) — adversarial evals, clean-install
  gates, smoke, example, and honest integration documentation.

## Provisional OpenAI Architecture

Use a direct Responses adapter, not the Agents SDK, for this slice. The host
runner, tool authority, lifecycle, and retry semantics already belong to the
harness; adopting an SDK-owned agent loop would create a second authority and
state owner. This decision must be checked against current official OpenAI
documentation before TUT-06D implementation. Any material mismatch requires a
spec/ADR review, not a quiet adapter-side behavior branch.

## Verification

- Offline scripted host end-to-end, adapter conformance, opt-in configured-model
  Responses smoke, clean install with and without the optional extra, and
  architecture gates.
