# Task Bead: TUT-03C2B gateway integration and scripted evals

Status: Ready
Priority: P0
Type: expand
Depends On: TUT-03C2A

## Outcome

Both built-in packages execute through the authority-bound gateway under
deterministic scripted models, including direct and clarified tutor turns.

## Acceptance Criteria

- [ ] Direct sufficient requests complete without dialogue; materially
  ambiguous requests suspend once and resume from the same bound generation.
- [ ] Changed input, authority, dependency, or continuation is rejected or
  reported stale without executing a second model call.
- [ ] Insufficient/conflicting evidence terminates before dialogue/model work;
  process loss, cancellation, and structured-output fallback remain truthful.
- [ ] Prompt-injection-shaped evidence remains quoted data and cannot alter
  tools, policy, schema, or output provenance.
- [ ] Offline evals prove explanations are grounded and assessments expose
  questions only; the public seven-tool registry remains byte-identical.

## Verification

- Scripted-model gateway integration/evals, interruption/recovery cases, full
  offline suite, architecture checks, Ruff, strict mypy, and diff check.
