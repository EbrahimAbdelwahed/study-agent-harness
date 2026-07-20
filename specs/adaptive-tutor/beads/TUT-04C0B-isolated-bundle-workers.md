# Task Bead: TUT-04C0B isolated bundle worker execution

Status: Expanded by TUT-04C0B1B
Priority: P0
Type: expand
Depends On: TUT-04C0

## Outcome

Provider-neutral fresh-context worker primitives and a lesson-specific resumable
fan-out coordinator isolate generation from the tutor conversation.

## Child Beads

- [TUT-04C0B1 — isolated generation worker primitive](TUT-04C0B1-isolated-worker-primitive.md)
- [TUT-04C0B1A — gateway-worker proof adapter](TUT-04C0B1A-gateway-worker-proof-adapter.md)
- [TUT-04C0B2 — lesson fan-out and recovery](TUT-04C0B2-lesson-worker-fanout.md)
- [TUT-04C0B1B — profiled worker execution commitments](TUT-04C0B1B-profiled-worker-execution.md)

## Acceptance Criteria

- [ ] B1 defines the generic allowlisted task/receipt boundary and proves every
  model request starts without tutor history, unrelated materials, credentials,
  principal data, or provider-specific agent types.
- [ ] B2 executes a C0A lesson plan through stable child identities, bounded
  concurrency, ordered aggregation, checkpoint/resume, and compact host views.
- [ ] B1B preserves the five-field public task identity while binding the exact
  non-effect profile receipt through execution, resume, proof, and recovery.
- [ ] One child page remains bounded by the existing 24-candidate technical
  transport/review limit, with no lesson target or minimum.
- [ ] No child or coordinator can accept/publish artifacts, add a StudyTool, or
  write canonical learner state.

## Verification

- Primitive isolation and receipt contracts, lesson process-loss recovery,
  stale-plan/profile/source cases, architecture/tool parity, and full gates.

## Grilling Evidence

ADR-0010 fixes the isolation boundary. Architecture audit split the generic
worker primitive from lesson fan-out so each bead fits one worker and exam
analysis can reuse isolation without depending on lesson coordination.
