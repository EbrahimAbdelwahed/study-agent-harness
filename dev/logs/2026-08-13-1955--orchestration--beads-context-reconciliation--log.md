# Log: Beads and Cardine context reconciliation

Date: 2026-08-13 19:55 CEST
Area: orchestration, package adoption

## Summary

Reconciled the active Harness Beads graph against the integrated package-
foundation history and made the Cardine adoption boundary explicit in both
repositories. Closed 25 stale PF-05, PF-06, optional-package, and aggregate
records whose parent work is already represented by integrated commits.

The remaining graph is intentional: PF-11 is blocked by Cardine CA-08, and the
future-runtime HR lane is blocked by PF-11 and Cardine CA-10. Both external
gates remain deferred because the active Cardine checkout still contains
`src/study_agent` and does not declare `study-agent-harness`.

## Files Changed

- `CONTEXT.md`: recorded Harness `0.3.0` and the still-pending Cardine gates.
- `CONTEXT-MAP.md`: changed Cardine from a generic future consumer to a
  downstream consumer whose adoption is pending.
- Cardine `CONTEXT.md` and `dev/index.md`: corrected the canonical checkout and
  current-versus-target package boundary.

## Beads State

- Before reconciliation: 228 closed, 20 in progress, 18 open, 2 deferred.
- After reconciliation: 253 closed, 13 open, 2 deferred, none in progress.
- Remaining active records: PF-11, HR-01 through HR-12, and the deferred CA-08
  and CA-10 external gates.
- `br sync --status --json`: healthy, no dirty records after export.

The local `.beads/` directory is deliberately untracked in this worktree. This
log is the tracked durable record of the reconciliation; unrelated local agent-
mail files and configurations were not adopted into the branch.

## Verification

- `br show <CA-08|CA-10|PF-11> --json`: dependencies and deferred gates match
  the approved package-adoption order.
- `br blocked --json`: PF-11 remains blocked by CA-08; HR-01 remains blocked by
  PF-11 and CA-10; downstream HR records remain transitively blocked.
- Cardine inspection: 879 files remain under `src/study_agent`, and
  `pyproject.toml` has no `study-agent-harness` dependency.

## Notes

- Beads Rust `0.2.22` could not attest the schema-13 migration candidate. The
  source database was preserved and reconciliation used compatible `br 0.2.16`.
  Do not replace the healthy database with the rejected recovery candidate.
- The original Cardine bead database containing
  `cardine-harness-program-ca-08-wio` and `cardine-harness-program-ca-10-xbv`
  was not present in the recovered local checkouts. The Harness mirror gates
  therefore remain the available source of orchestration truth.
