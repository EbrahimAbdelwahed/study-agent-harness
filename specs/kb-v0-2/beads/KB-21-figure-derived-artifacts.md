# KB-21: Optional figure cards and surrogates

Status: Proposed — provider/prompt decisions required
Risk: High
Depends On: KB-18, KB-20
Parent coverage: §§9.4, 14, 16; M8

## Outcome

Optional provider-neutral workers create versioned figure cards and
clearly-labeled surrogates only where measured value justifies them, with exact
lineage to the figure citation.

## API seam

- Closed `FigureCard` kind/role/depicts/description contract.
- `FigureSurrogate` contract always names its figure citation and derived
  provenance.
- `essential|illustrative|decorative` classification has a versioned policy,
  confidence/review state, and conservative failure behavior.
- Prompt/model invocation stays behind existing generic model/worker ports.

## Acceptance criteria

- [ ] Artifact IDs bind input figure, model/provider-neutral identity, prompt
  version, policy, and output.
- [ ] Surrogates are generated only for accepted `essential` decisions.
- [ ] A wrong/unknown role cannot silently hide canonical figure access.
- [ ] Derived descriptions are never cited as fact and are labeled in every
  evidence row.
- [ ] Retry/resume is idempotent and artifacts invalidate independently.
- [ ] Each staged addition earns value against the figure evals.

## Verification

- Scripted-model contract, malformed-output, prompt-injection, lineage,
  invalidation, and recovery tests.
- Separate eval deltas for card, role classifier, and surrogate.
- Provider adapter/security review; no live-network default tests.

## Out of scope

- Image generation, direct image embeddings, tutor explanation, or UI rendering.
