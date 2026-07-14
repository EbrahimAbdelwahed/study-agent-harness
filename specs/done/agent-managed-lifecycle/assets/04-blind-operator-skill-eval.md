# Blind operator-skill eval

Date: 2026-07-13
Evaluator context: fresh subagent with no conversation history
Network/credentials: denied / absent
Checkout mutation: forbidden

## Prompt shape

Use the packaged skill as the sole workflow guide from a blank directory;
attempt discovery, initialization, course/source population, verification,
stable session, retry guidance, and export. Report commands, outcomes, and
ambiguities. The expected solution was not provided.

## Outcome

- Completed `describe` and verified `agent-operations@1`, version 0.1.1, the
  exact seven StudyTools, and extracted-skill SHA-256 parity.
- Completed offline init, one course, two explicit UTF-8 sources, `doctor`,
  stable session start/retry/get, tool discovery, and two byte-identical exports
  at the same high-water mark.
- Correctly skipped `ask` because no model adapter was configured.
- Correctly did not attempt the 0.2 manifest recovery commands because they were
  not advertised by 0.1.1.

## Findings applied

- Clarified that the skill operates an installed distribution.
- Prescribed repository-relative, non-symlink source paths with
  `--repository .` from the repository directory.
- Clarified that export output is a checksummed directory tree, not one JSON file.

## Release follow-up

The evaluator listed tools but did not invoke one through an embedding host.
Independent review therefore required the installed external-agent example and
CI journey to exercise an offline StudyTool before 0.1.1 approval.
