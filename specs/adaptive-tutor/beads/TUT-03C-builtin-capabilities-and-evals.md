# Task Bead: TUT-03C built-in tutor capabilities and offline evals

Status: Blocked on TUT-03B
Priority: P0
Type: expand
Depends On: TUT-03B

## Outcome

`explain_concept@1` and `assess_understanding@1` ship as portable skill and
playbook packages behind the gateway, with deterministic scripted-model evals.

## Acceptance Criteria

- [ ] Each capability pins skill, playbook, prompt, schemas, validators, and
  read-dependency construction without provider/model selectors.
- [ ] Explanation acts from sufficient current evidence and suspends only for
  a clarification that materially changes the bounded task.
- [ ] Assessment produces questions or evidence-safe termination; grading,
  attempts, and mastery remain deferred to TUT-05.
- [ ] Direct action, minimal clarification, changed input, interruption,
  resume, and unsupported evidence are covered offline.
- [ ] Packages cannot self-register tools or write learner facts.

## Verification

- Contract tests, scripted-model evals, gateway/playbook integration,
  architecture checks, and full gates.
