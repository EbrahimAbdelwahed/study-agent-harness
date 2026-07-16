# Task Bead: TUT-06A provider-neutral tutor-host contracts

Status: Blocked on TUT-05E
Priority: P0
Type: tracer-bullet
Depends On: TUT-03, TUT-05E

## Outcome

Strict provider-neutral host contracts compose the exact tutor snapshot,
learner-evidence view, advertised capability manifests, pending continuation,
and host-file descriptors into one redacted decision context without granting
the decision adapter authority or persistence access.

## Acceptance Criteria

- [ ] A `TutorHostContext` binds course/session, tutor-snapshot high-water
  sequence, learner-evidence through-sequence, ordered advertised capability
  identities/fingerprints, optional pending continuation descriptor, and
  ordered opaque host-file descriptors.
- [ ] The context has one strict deterministic JSON projection and
  domain-separated fingerprint. It is assembled from `TutorSnapshotPort`, the
  TUT-05E `LearnerEvidenceViewPort`, and gateway discovery without modifying
  `TutorSnapshotV1` or either projection owner.
- [ ] The model-facing projection is structurally unable to contain local
  paths, credentials, principal ids, grants, correlation/idempotency keys, raw
  prompts/traces, provider configuration, canonical hidden assessment answers,
  or unapproved file bytes.
- [ ] One closed `TutorDecision` union supports only: start one advertised
  capability with public manifest inputs; answer one exact pending dialogue;
  ask the learner one bounded question; return one bounded assistant message;
  or stop with a closed reason.
- [ ] A start decision cannot name repository, principal, course/session,
  grants, model, retry, or provider. A dialogue decision binds the exact opaque
  pending-continuation fingerprint and contains only the schema-bounded learner
  response.
- [ ] `TutorDecisionPort` accepts the redacted context and a host-issued
  interruption token and returns only the closed decision union. It has no
  gateway, event-store, model-playbook, ingestion, filesystem, or canonical
  write method.
- [ ] Host action identities and retry receipts are trusted, opaque,
  fingerprint-bound values outside the decision schema. Model text cannot mint
  or alter them.
- [ ] Context/decision codecs reject unknown fields, noncanonical order,
  changed fingerprints, unadvertised capabilities, invalid public inputs,
  stale continuation identity, secret/path-shaped fields, and oversized text.
- [ ] No OpenAI, agent SDK, provider, adapter, UI, CLI, or `sbobby-web` import
  enters domain, state, skills, playbooks, capabilities, assessment, or tutor
  snapshot owners.

## Verification

- Contract/codec/fingerprint/redaction tests; provider and authority injection
  fixtures; architecture imports; existing tutor snapshot, learner evidence,
  and gateway contracts; Ruff; strict mypy.

## Worker Briefs

- [Production](../worker-briefs/TUT-06A-production.md)
- [Tests](../worker-briefs/TUT-06A-tests.md)
