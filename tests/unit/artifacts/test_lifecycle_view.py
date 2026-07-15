from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from study_agent.artifacts.view import ProjectionArtifactView
from study_agent.domain import ArtifactDecision, ArtifactId, EventId, StudyArtifactKind
from study_agent.domain._validation import JsonValue
from study_agent.state import Projection, apply_event
from tests.unit.artifacts.test_lifecycle_events import COURSE, decision_event
from tests.unit.artifacts.test_lifecycle_projection import proposed_pair, registry


def test_view_replays_history_pending_batches_and_command_receipts() -> None:
    projection, framework, detail = proposed_pair()
    view = ProjectionArtifactView(lambda course_id: projection)
    snapshot = view.get(COURSE)

    assert snapshot.sequence == 2
    assert tuple(item.id for item in snapshot.pending()) == tuple(
        sorted((framework.revision_id, detail.revision_id), key=str)
    )
    assert snapshot.accepted() == ()
    assert snapshot.history(detail.artifact_id)[0].parent_artifact_id == framework.artifact_id
    assert snapshot.batches[0].revision_ids == (
        framework.revision_id,
        detail.revision_id,
    )
    assert view.command_fingerprint(COURSE, projection_event_id(projection)) is not None


def projection_event_id(projection: Projection) -> EventId:
    artifacts = cast(Mapping[str, JsonValue], projection.state["study_artifacts"])
    commands = cast(Mapping[str, JsonValue], artifacts["commands"])
    return EventId(next(iter(commands)))


def test_view_preserves_durable_decisions_accepted_by_kind_and_parent_lookup() -> None:
    projection, framework, detail = proposed_pair()
    projection = apply_event(
        projection,
        replace(
            decision_event(framework.revision_id, ArtifactDecision.ACCEPT, key="framework"),
            course_sequence=3,
        ),
        registry(),
    )
    projection = apply_event(
        projection,
        replace(
            decision_event(detail.revision_id, ArtifactDecision.ACCEPT, key="detail"),
            course_sequence=4,
        ),
        registry(),
    )
    snapshot = ProjectionArtifactView(lambda course_id: projection).get(COURSE)

    assert snapshot.pending() == ()
    assert tuple(item.id for item in snapshot.accepted(StudyArtifactKind.FLASHCARD)) == tuple(
        sorted((framework.revision_id, detail.revision_id), key=str)
    )
    assert tuple(item.revision_id for item in snapshot.decisions) == (
        framework.revision_id,
        detail.revision_id,
    )
    assert tuple(item.id for item in snapshot.children(framework.artifact_id)) == (
        detail.revision_id,
    )
    assert snapshot.children(ArtifactId("batch-local-ordinal-0")) == ()


def test_view_fails_closed_for_wrong_course_and_projection_corruption() -> None:
    projection, _, _ = proposed_pair()
    wrong = ProjectionArtifactView(
        lambda course_id: replace(projection, course_id=type(COURSE)("other-course"))
    )
    with pytest.raises(ValueError, match="another course"):
        wrong.get(COURSE)

    corrupt = replace(
        projection,
        state={**projection.state, "study_artifacts": {"unexpected": True}},
    )
    with pytest.raises(ValueError, match="corrupt"):
        ProjectionArtifactView(lambda course_id: corrupt).get(COURSE)
