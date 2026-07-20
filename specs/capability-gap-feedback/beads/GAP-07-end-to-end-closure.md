# Task Bead: GAP-07 adversarial end-to-end closure

Status: Approved — blocked on GAP-03 and GAP-06 implementation
Priority: P1
Type: contract
Depends On: GAP-03, GAP-06

## Outcome

The local limitation-to-decision-to-promotion loop is proven safe, replayable,
useful, and independent of optional converter or GitHub adapters.

## Slice Strategy

contract

Fresh Context Fit: yes

## Spec Coverage

- Complete MVP acceptance criteria and operational documentation.

## Grilling Evidence

- Session/artifact: all MVP bead reports and decisions.
- Decision state: scope approved 2026-07-18; implementation dependencies remain.
- ADR/glossary changes: confirm ADR-0011 remains accurate.

## Worker Profile

reuse `test-engineer`, `security-reviewer`, and `reviewer`

Rationale: independent cross-owner verification; no new behavior unless a finding
is separately approved.

## Acceptance Criteria

- [ ] Offline unsupported-format story produces honest fallback, one local
  aggregate, redacted proposal, one decision, and correct accepted/rejected path.
- [ ] Duplicate learners/sessions, spoofed MIME/extension, malicious filenames/
  content, prompt injection, secrets, rate pressure, retries, races, and process
  loss remain safe and deterministic.
- [ ] No canonical-course contamination, eighth StudyTool, provider/Flywheel
  or network dependency in core, automatic implementation before approval, or
  network use in default tests.
- [ ] Documentation explains local consent/export, maintainer authority,
  retention, resolution, and how a host integrates the tool.

## Verification

- Full offline suite, architecture/tool parity, secret scan, deterministic
  replay/export, wheel, Python 3.12/3.13, and independent semantic/security audit.

## Out Of Scope

- GAP-04B converter, GAP-07B hosted transport closure, and GAP-08 GitHub
  synchronization.
