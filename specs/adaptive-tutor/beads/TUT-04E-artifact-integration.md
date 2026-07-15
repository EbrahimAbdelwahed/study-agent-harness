# Task Bead: TUT-04E verified commit and export integration

Status: Blocked on TUT-04A and TUT-04B
Priority: P0
Type: contract
Depends On: TUT-04A, TUT-04B

## Outcome

Generated proposal commits use verified capability output, and artifact history
survives repository replay plus explicit credential-free export v2.

## Child Beads

- [TUT-04E1 — verified generated-batch commit](TUT-04E1-verified-artifact-commit.md)
- [TUT-04E2 — artifact replay and export v2](TUT-04E2-artifact-export-v2.md)

## Acceptance Criteria

- [ ] Generated commits retrieve verified run output and resolve temporary graph
  keys to canonical identities without exposing a raw bypass.
- [ ] Runtime composition roots replay artifact events and old repositories.
- [ ] Existing export v1 golden bytes/file set remain unchanged; explicit v2
  retains artifact history and public provenance with required redaction.
- [ ] Exact seven StudyTools and prior capability contracts remain unchanged.

## Verification

- Verified commit, replay, v1 non-regression, v2 determinism/redaction,
  architecture/tool parity, wheel, Python 3.12/3.13, full gates.
