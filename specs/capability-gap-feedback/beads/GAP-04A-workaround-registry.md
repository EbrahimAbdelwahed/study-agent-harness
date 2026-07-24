# Task Bead: GAP-04A allowlisted workaround registry and receipts

Status: In progress — P1 execution/approval hardening implemented; closure remains
Priority: P2
Type: expand
Depends On: GAP-00

## Outcome

Hosts can describe versioned temporary strategies with explicit preconditions,
effects, approvals, provenance, and quality limitations instead of letting an
agent invent arbitrary converters or commands.

## Slice Strategy

expand

Fresh Context Fit: yes

## Spec Coverage

- Safe workaround search/selection boundary and truthful receipts.

## Grilling Evidence

- Session/artifact: ADR-0011 threat model.
- Decision state: scope approved 2026-07-18; no unresolved generic-contract decision.
- ADR/glossary changes: workaround strategy/receipt.

## Worker Profile

reuse `architect` then `implementer`; require `security-reviewer`

Rationale: reusable execution-authority contract with supply-chain risk.

## What To Do

- Define static host-installed strategy manifests with input/output kinds,
  effect/network/credential declarations, approval policy, and quality warnings.
- Separate search/selection from execution; the registry cannot load dynamic
  code, shell strings, plugins, packages, or remote instructions.
- Produce `not_available|requires_approval|attempted_succeeded|
  attempted_failed` receipts with derived-artifact provenance.

## Acceptance Criteria

- [ ] Uninstalled or ungranted strategies cannot be selected or reported as run.
- [ ] Original material remains immutable and derived output names exact
  provenance and known quality loss.
- [ ] Network, credentials, executable payloads, and hidden effects fail closed.

## Verification

- Manifest/authority/effect/approval/provenance/adversarial architecture tests.

## Out Of Scope

- Any concrete converter, dynamic plugin installation, or web search.
