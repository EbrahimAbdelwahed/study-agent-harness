# Task Bead: TUT-06 OpenAI reference tutor host

Status: Blocked on TUT-03 and TUT-05
Priority: P0
Type: tracer-bullet
Depends On: TUT-03, TUT-05

## Worker Profile

reuse `model-adapter-worker`; create `reference-tutor-host-worker` after current
OpenAI Responses and Agents SDK documentation is captured

## Outcome

An optional OpenAI reference host uses GPT-5.6 to choose capabilities from a
sequence-consistent tutor snapshot with bounded steps and trusted authority.

## Acceptance Criteria

- [ ] OpenAI imports are confined to optional host/technical adapter packages.
- [ ] Scripted and live hosts exercise the same gateway contract.
- [ ] Step budget, interruption, stale continuation, retry, and redaction are explicit.
- [ ] File uploads become host-bound snapshots before agent visibility.
- [ ] API-key mode is complete; subscription mode is not falsely emulated.

## Verification

- Offline scripted host end-to-end, adapter conformance, opt-in GPT-5.6 smoke,
  clean install, architecture gates.
