# Worker Brief: AML-05 tests

## Assignment

After the AML-05 production contract is stable, add independent contract,
effect-firewall and architecture coverage. Do not edit production.

## Scope

You may change:

- `tests/contract/lifecycle/test_manifest_contract.py`
- `tests/contract/cli/test_manifest_commands.py`
- `tests/architecture/test_lifecycle_boundaries.py`
- only existing CLI help/discovery expectation tests that must list the two new
  additive commands

Do not change production, fixtures/specs/docs, other behavior tests, commits or push.

## Required Coverage

- Golden canonical bytes and domain-separated digest, reordered input parity,
  course/source ID sorting, goal/style order preservation and deep immutability.
- Exact lower/upper bounds and bound+1 for every normative count/string/size.
- Duplicate keys/IDs, unknown/missing fields, bool-as-int, invalid UTF-8,
  non-finite numbers, date and lexical path attacks.
- Deep, wide, excessive-node and recursive settings failures through the one
  safe manifest validation error without input/secret echo.
- Secret-like, behavioral, authority and executable settings vocabulary.
- Schema without reading a default file; explicit/default validate; declared
  missing source accepted; repository/model/socket hooks fail if touched;
  filesystem unchanged except reading the explicit manifest.
- Lifecycle dependency direction and unchanged exact-seven StudyTool surface.

## Verification

Run focused pytest, Ruff and strict mypy for the allowed tests; report exact
outcomes and gaps. Do not commit or push.
