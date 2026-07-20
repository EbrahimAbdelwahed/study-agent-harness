# Worker Brief: TUT-02A tests

## Goal

Independently pin observable TUT-02A behavior without modifying production.

## Allowed Files

- `tests/unit/sessions/test_conversation_turn_events.py`
- `tests/contract/session/test_conversation_turn_contract.py`
- `tests/integration/test_session_conversation_turns.py`

## Required Coverage

- Strict `tutor_message@1` and event envelope codecs.
- Learner/assistant authority, active session, reply ownership, verified status.
- Exact retry, changed retry, stale/race, run uniqueness.
- Old projection byte identity and mixed replay/rebuild.
- Local composition, lifecycle/export compatibility, seven-tool stability.

## Verification

- One test at a time through public services/views, then focused suite, Ruff,
  strict mypy where supported, and diff check.
