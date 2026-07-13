# Slice 04: Operator skill and 0.1.1 release

Release: 0.1.1
Depends on: slices 01–03, with slices 02 and 03 independently depending on 01

## Contract unlocked

A fresh generic agent can install the wheel and complete setup, population,
verification, explicit-session use, retry, recovery, and export by following a
versioned operator skill rather than a model-specific adapter.

## API seam

- `src/study_agent/operator_skill/SKILL.md`: host-operational playbook packaged
  in the wheel with stable ID, version, and checksum.
- `pyproject.toml` package data includes
  `study_agent.operator_skill = ["SKILL.md"]`; no second top-level copy is kept.
- CLI `operator skill --output PATH`: extracts the exact packaged resource
  offline and returns a machine-readable receipt; `describe` exposes its
  identity without duplicating its content.
- Updated `docs/examples/external_agent.py`: blank-project journey and capability
  negotiation without hard-coding a provider or assuming a preconfigured model.
- README agent quickstart and stable JSON/error/retry documentation.

The operator skill may choose safe commands and reconcile results. It must not
contain grounded-answer prompt content, pedagogical policy, retrieval ranking,
or provider branches.
For 0.2 lifecycle recovery it must prescribe `status → plan → apply
--expect-plan NEW_SHA` after interruption or lost output; blindly replaying an
old plan is not the recovery algorithm.

## Runnable checkpoint

From a clean wheel and empty directory, an unprimed worker follows the skill to:

1. discover the contract;
2. initialize offline;
3. create/list a course;
4. add/list explicit `.txt`/`.md` sources;
5. run doctor;
6. start a stable session;
7. inspect/invoke offline tools and optionally ask through the generic adapter;
8. retry after simulated lost output;
9. export and verify deterministic output.

## Verification

- Blind skill eval with no conversation context.
- Clean-wheel test starts in an empty directory, extracts the skill using only
  the installed distribution, and verifies its checksum before following it.
- Wheel-content test asserts the single packaged skill resource is present and
  byte-identical to the resource returned by the extraction command.
- Clean-wheel Python 3.12 and 3.13 end-to-end process fixtures.
- Default flow denies network and requires no credential.
- Optional scripted/OpenAI-compatible ask uses the same generic contract.
- Full pytest, Ruff, strict mypy, build, install, CLI, `py.typed`, public-hygiene,
  and independent semantic/security review gates.

## Human review checkpoint

Approve the operator workflow and vocabulary before tagging 0.1.1. This is a
non-visual review; no screenshot gate applies.
