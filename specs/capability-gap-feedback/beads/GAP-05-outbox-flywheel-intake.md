# Task Bead: GAP-05 outbox-to-proposal parent

Status: Approved parent — child beads own implementation
Priority: P1
Type: parent
Depends On: GAP-02

## Outcome

Strict local reports cross a one-way portable boundary into scoped Flywheel
proposals without introducing a harness-core dependency on the devkit.

## Child Beads

- [GAP-05A — strict redacted harness outbox](GAP-05A-harness-outbox.md)
- [GAP-05B — devkit import and reproduction](GAP-05B-devkit-import-reproduction.md)
- [GAP-05C — scoped proposal and decision](GAP-05C-proposal-decision.md)
- [GAP-05D — hosted private intake transport](GAP-05D-private-intake-transport.md)

## Acceptance Criteria

- [ ] Dependency direction is `devkit -> portable bundle schema`; harness core
  imports no Flywheel, GitHub, `br`, or devkit package.
- [ ] One immutable proposal and decision covers exactly one gap key or an
  explicitly reviewed equivalent cohort; unrelated gaps remain separate.
- [ ] A/B/C and all defaults perform no external network work. D may perform only
  explicitly configured authenticated delivery to the private inbox; no child
  starts feature implementation before approval.

## Out Of Scope

- Worker dispatch; use the independently fresh-context child beads.
