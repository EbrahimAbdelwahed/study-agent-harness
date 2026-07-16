# Task Bead: TUT-04C0B1A gateway-worker proof adapter

Status: Done
Priority: P0
Type: expand
Depends On: TUT-03, TUT-04C0B1

## Worker Profile

Reuse `grounded-study-artifact-worker`; require independent contract tests for
trace-to-receipt conversion, restart/race ownership, and proof redaction.

## Outcome

A provider-neutral adapter drives one trusted gateway run as a
`ChildCapabilityObservation` and atomically preserves the sanitized execution
proof required by TUT-04D and TUT-04E1.

## Acceptance Criteria

- [ ] `IsolatedCapabilityRunPort.resume` receives the exact stored task with the
  continuation/response/context; B1 passes it from durable state. No task
  registry or hidden lookup is introduced.
- [ ] The adapter maps every closed gateway outcome without directly invoking a
  model, validator, tool, or playbook. Its transient completed observation keeps
  the recovered `VerifiedRunRecord` required by B1 verification.
- [ ] Engine, gateway, dispatch, and worker task factories use one public pure
  playbook-definition fingerprint helper; B1 and proof use one public pure
  worker-authority fingerprint helper. Existing bytes remain unchanged.
- [ ] Durable `VerifiedChildExecutionProof` contains only run/status/definition/
  pins, input fingerprint, exact public output, ordered dependencies,
  allowlisted completed tool outputs, bounded technical model receipt, prompt
  receipt, and validation receipts. It stores no `VerifiedRunRecord`, raw trace,
  raw input, or other step output.
- [ ] One atomic owner slot keyed by child run binds authority, task, expected B1
  completed-receipt fingerprint, and proof. Exact retry is identical; competing
  proof/receipt/authority conflicts. Lookup requires the exact task and completed
  receipt; task bytes and raw capability inputs are never persisted in the slot.
- [ ] Codec, size, or proof-store failure yields a sanitized failed observation
  before B1 persists completion. Crash/restart/race recovery never repeats a
  durable child effect or exposes a partial proof.
- [ ] Proof never widens B1 compact/detail, emits canonical state, grants artifact
  authority, or imports provider SDK behavior.

## Scope

- Gateway adapter, worker proof package/ports, public fingerprint helpers, and
  the narrow B1 resume call correction.
- No exam/flashcard policy, fan-out, artifact commit, UI, StudyTool, provider
  adapter, dependency, or `sbobby-web` change.

## Verification

- Outcome/provenance mapping, resume task identity, golden fingerprints, exact
  codec/redaction, atomic create/retry/conflict/restart/race, failure-before-
  completion, Ruff, strict mypy, tool parity, and full offline gates.

## Grilling Evidence

B1 intentionally exposes only verified public output. D/E1 additionally need a
durable prepared-tool/dependency/provenance chain. B1A supplies the minimum
sanitized proof without persisting the complete engine run.
