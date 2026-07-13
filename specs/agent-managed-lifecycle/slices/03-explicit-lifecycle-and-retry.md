# Slice 03: Explicit lifecycle and retry

Release: 0.1.1
Depends on: slice 01

## Contract unlocked

An automation host can enumerate courses, explicitly start a session, verify
its identity, and retry a first ask after lost output without creating a second
session or answer.

## API seam

- CLI `course list`: deterministic projection-backed course manifests.
- CLI `session start COURSE_ID --session-id SESSION_ID`: delegates to the
  existing idempotent `SessionService.start()`.
- CLI `session get COURSE_ID SESSION_ID`: read-only lifecycle/status receipt.
- Operation descriptors mark automatic-session `ask` as convenience-only and
  explicit session plus idempotency identities as the agent-safe path.

No lifecycle command becomes a StudyTool. The host supplies session and
idempotency identities; model arguments cannot supply or override them.

## Runnable checkpoint

```bash
study-agent --json --repository REPO course list
study-agent --json --repository REPO session start COURSE --session-id SESSION
study-agent --json --repository REPO ask COURSE QUESTION \
  --session-id SESSION --idempotency-key REQUEST
study-agent --json --repository REPO session get COURSE SESSION
```

Rerunning the sequence after discarding the first ask response converges on the
same canonical answer and performs no second completed model effect.

## Verification

- Empty and populated deterministic course-list tests.
- Session start first call, retry, scoped identity, and process restart.
- Session identity is the pair `(course_id, session_id)`: retrying the same pair
  is a noop; the same session text under another course is a distinct session
  and requires no global uniqueness index.
- Lost-stdout process test with stable session/key and one model invocation.
- Same idempotency key with a changed question fails closed.
- Authority-shaped keys remain rejected from model arguments.
- Existing automatic-session ask behavior remains compatible.
- Exit codes and JSON errors identify retryable versus non-retryable conflicts.

## Human review checkpoint

Review only the external lifecycle and retry semantics. A request to derive
authority from model JSON or silently change legacy ask behavior invalidates the
slice.
