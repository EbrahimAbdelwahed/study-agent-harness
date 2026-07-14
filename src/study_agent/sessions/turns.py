"""Strict derivation of canonical tutor messages from verified playbook runs."""

from __future__ import annotations

from collections.abc import Mapping

from study_agent.domain import (
    AssistantTurnStatus,
    InteractionId,
    VerifiedRunOutputRef,
)
from study_agent.domain._validation import JsonValue
from study_agent.playbooks import PlaybookRunStatus, VerifiedRunRecord

from .events import tutor_message_output_fingerprint
from .service import SessionCommandError


def verified_tutor_message(
    run: VerifiedRunRecord,
) -> tuple[
    AssistantTurnStatus,
    str,
    InteractionId | None,
    VerifiedRunOutputRef,
]:
    if not isinstance(run, VerifiedRunRecord):
        raise TypeError("run must be a VerifiedRunRecord")
    raw = run.outputs.get("tutor_message")
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema_version",
        "status",
        "content",
        "in_reply_to_interaction_id",
    }:
        raise SessionCommandError("verified run requires an exact tutor_message@1 output")
    if raw.get("schema_version") != 1 or isinstance(raw.get("schema_version"), bool):
        raise SessionCommandError("verified tutor_message schema version is unsupported")
    status_raw = raw.get("status")
    content = raw.get("content")
    reply_raw: JsonValue | None = raw.get("in_reply_to_interaction_id")
    if not isinstance(status_raw, str):
        raise SessionCommandError("verified tutor_message status is invalid")
    try:
        status = AssistantTurnStatus(status_raw)
    except ValueError as error:
        raise SessionCommandError("verified tutor_message status is unsupported") from error
    expected = (
        AssistantTurnStatus.TERMINATED
        if run.status is PlaybookRunStatus.TERMINATED
        else AssistantTurnStatus.COMPLETED
    )
    if status is not expected:
        raise SessionCommandError("verified tutor_message status disagrees with run status")
    if not isinstance(content, str) or not content or content != content.strip():
        raise SessionCommandError("verified tutor_message content is invalid")
    if reply_raw is not None and (
        not isinstance(reply_raw, str) or not reply_raw or reply_raw != reply_raw.strip()
    ):
        raise SessionCommandError("verified tutor_message reply linkage is invalid")
    reply = InteractionId(reply_raw) if isinstance(reply_raw, str) else None
    fingerprint = tutor_message_output_fingerprint(status, content, reply)
    return status, content, reply, VerifiedRunOutputRef(run.run_id, fingerprint)
