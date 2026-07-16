# Worker Brief: TUT-06A tests

## Goal

Independently pin the provider-neutral tutor-host context, decision union,
authority exclusion, exact codecs, redaction, and import boundaries.

## Allowed Files

- `tests/unit/hosts/test_contracts.py`
- `tests/unit/hosts/test_context.py`
- `tests/contract/hosts/test_tutor_decision_port.py`
- `tests/architecture/test_tutor_host_boundaries.py`

## Forbidden Files

- All production files, other tests, docs/specs, dependencies, adapters,
  OpenAI/agent SDK/provider code, runner behavior, file capture, UI,
  `sbobby-web`, and configuration.

## Required Coverage

- Golden host context composition binds exact tutor high-water and learner-
  evidence sequence, sorted advertised manifest identities/fingerprints,
  pending continuation fingerprint, and ordered opaque file descriptors.
- Canonical JSON/bytes/fingerprint round trips are byte-identical. Reordering,
  missing/extra fields, duplicate identities, changed digest/sequence/schema,
  malformed enums, and oversized content fail closed.
- Start decisions accept only currently advertised capability ids and exact
  public manifest inputs. Dialogue decisions bind the exact pending descriptor;
  changed or absent pending identity fails.
- Ask/message/stop variants have exact bounded schemas and cannot smuggle
  arbitrary tools, persistence commands, provider selection, or authority.
- Adversarial fixtures try credentials, API keys, endpoints, local paths,
  filenames with traversal, principal ids, grants, course/session override,
  correlation/idempotency/retry keys, hidden answers/rubrics, raw prompts/traces,
  provider payloads, and unknown capability inputs. Each is structurally absent
  or rejected before a decision adapter call.
- Decision-port conformance proves it receives only redacted context plus an
  interruption token and returns only a closed decision, with no effect method.
- Architecture tests forbid host imports from domain/state/skills/playbooks/
  capabilities/assessment/tutor-snapshot owners and forbid provider/SDK/UI/CLI
  imports from the neutral host package. The seven StudyTools remain unchanged.

## Verification

- New focused tests.
- Existing tutor snapshot, learner evidence, capability contract, and public
  tool tests.
- `.venv/bin/ruff check <allowed test files>`
- `git diff --check`

## Report

Report semantic mismatches and leaked authority/redaction fields as concrete
findings. Do not edit production, commit, or delegate.
