"""Typed event-sourced study sessions and bounded continuation context."""

from .events import (
    SESSION_ANSWER_RECORDED,
    SESSION_CONTINUATION_SUMMARY_UPDATED,
    SESSION_ENDED,
    SESSION_EVENT_TYPES,
    SESSION_INTERACTION_RECORDED,
    SESSION_RESUMED,
    SESSION_SCHEMA_VERSION,
    SESSION_STARTED,
    SESSION_SUSPENDED,
    answer_recorded_payload,
    decode_answer_recorded,
    decode_interaction_recorded,
    decode_session_started,
    decode_summary_updated,
    interaction_recorded_payload,
    lifecycle_payload,
    session_started_payload,
    summary_payload,
)
from .projection import register_session_events
from .provenance import ProvenanceAssemblyError, assemble_grounded_answer
from .service import (
    GroundedSessionFinalizer,
    IdempotencyConflictError,
    RetryableSessionConflictError,
    SessionCommandError,
    SessionService,
    StateWritePolicyError,
)
from .summary import (
    MAX_RECENT_EXCHANGES,
    MAX_SUMMARY_CHARACTERS,
    build_continuation_summary,
    verify_continuation_summary,
)
from .view import ProjectionSessionView

__all__ = [
    "MAX_RECENT_EXCHANGES",
    "MAX_SUMMARY_CHARACTERS",
    "SESSION_ANSWER_RECORDED",
    "SESSION_CONTINUATION_SUMMARY_UPDATED",
    "SESSION_ENDED",
    "SESSION_EVENT_TYPES",
    "SESSION_INTERACTION_RECORDED",
    "SESSION_RESUMED",
    "SESSION_SCHEMA_VERSION",
    "SESSION_STARTED",
    "SESSION_SUSPENDED",
    "GroundedSessionFinalizer",
    "IdempotencyConflictError",
    "ProjectionSessionView",
    "ProvenanceAssemblyError",
    "RetryableSessionConflictError",
    "SessionCommandError",
    "SessionService",
    "StateWritePolicyError",
    "answer_recorded_payload",
    "assemble_grounded_answer",
    "build_continuation_summary",
    "decode_answer_recorded",
    "decode_interaction_recorded",
    "decode_session_started",
    "decode_summary_updated",
    "interaction_recorded_payload",
    "lifecycle_payload",
    "register_session_events",
    "session_started_payload",
    "summary_payload",
    "verify_continuation_summary",
]
