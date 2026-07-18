# Worker Brief: TUT-06E reference-host closure

## Assignment

Close TUT-06 only after D is green. This is an additive offline demo/eval/docs
slice; do not redesign B-D.

## Allowed Files

- `examples/reference_tutor_host.py`.
- `tests/integration/test_reference_tutor_host_demo.py`.
- `tests/evals/test_reference_tutor_host_adversarial.py`.
- `tests/architecture/test_tutor_host_boundaries.py`: additive closure gates.
- `README.md` and `docs/reference-tutor-host.md`.

## Required Behavior

- A deterministic offline demo performs free-form learner entry, progressive
  context, capability discovery, one direct completion, one clarification
  suspend/resume, learner-evidence refresh, and trusted capture of one `.md`
  fixture. It must run without OpenAI SDK/network/key.
- Recorded Responses fixtures drive the same runner/gateway contract and exact
  TutorDecision values as the scripted adapter; no separate orchestration path.
- Adversarial tests compose existing B/C/D fixtures for authority/grant/idempotency
  injection, hidden answers, prompt/tool injection as inert content, forged and
  cross-owner continuation/file references, stale/retry/provider failure,
  budgets, and interruption. Do not duplicate every lower-level unit test.
- Documentation states API-key setup, optional extra, configurable model,
  network/cost/privacy expectations, trusted host duties, retry/stale/file
  semantics, and explicit lack of ChatGPT subscription support.
- Architecture keeps exactly seven StudyTools, one gateway/state owner, and
  optional SDK imports outside core.

## Stop Conditions

Stop if closure needs a CLI/product UI, new canonical event, new StudyTool,
network in default tests, PDF/OCR/audio, or changes outside the allowlist.
